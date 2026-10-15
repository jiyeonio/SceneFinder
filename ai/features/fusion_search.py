from pathlib import Path

from functools import lru_cache
from sentence_transformers import SentenceTransformer

@lru_cache(maxsize=1)
def get_semantic_model(model_type="base"):
    """
    base: 기존 다국어 MiniLM
    finetuned: AI-Hub 한국어 데이터로 추가 학습한 MiniLM
    """
    import os

    if model_type == "base":
        model_path = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

    elif model_type == "finetuned":
        model_path = os.environ.get("SCENEFINDER_MINILM_MODEL_PATH")

        if not model_path:
            raise ValueError(
                "Fine-tuned MiniLM 경로가 설정되지 않았습니다. "
                "SCENEFINDER_MINILM_MODEL_PATH 환경변수를 확인하세요."
            )

        if not Path(model_path).is_dir():
            raise FileNotFoundError(
                f"Fine-tuned MiniLM 모델 폴더가 없습니다: {model_path}"
            )

    else:
        raise ValueError(
            "model_type은 'base' 또는 'finetuned'만 가능합니다."
        )

    return SentenceTransformer(model_path)

from sentence_transformers import util
from ai.features.run_moment_detr_inference import predict_moments_hybrid

# temporal_iou는 아래에 별도로 정의


def temporal_iou(a, b):
    intersection = max(
        0,
        min(a["end_time"], b["end_time"])
        - max(a["start_time"], b["start_time"])
    )

    union = (
        max(a["end_time"], b["end_time"])
        - min(a["start_time"], b["start_time"])
    )

    return intersection / union if union > 0 else 0


def get_semantic_subtitle_candidates(
    query,
    subtitles,
    model,
    top_k=5
):
    windows = []

    for size in (1, 2, 3):
        for i in range(len(subtitles) - size + 1):
            group = subtitles[i:i + size]

            windows.append({
                "start_time": group[0]["start_time"],
                "end_time": group[-1]["end_time"],
                "text": " ".join(s["text"] for s in group)
            })

    embeddings = model.encode(
        [w["text"] for w in windows],
        convert_to_tensor=True
    )

    query_embedding = model.encode(
        query,
        convert_to_tensor=True
    )

    scores = util.cos_sim(
        query_embedding,
        embeddings
    )[0]

    candidates = []

    for idx in scores.topk(min(top_k, len(windows))).indices.tolist():
        w = windows[idx]

        candidates.append({
            **w,
            "score": round(scores[idx].item(), 4),
            "source": "subtitle"
        })

    return candidates



def select_subtitle_query(subtitles, korean_query, english_query):
    from langdetect import detect, DetectorFactory, LangDetectException

    DetectorFactory.seed = 0

    full_text = " ".join(
        str(item.get("text", ""))
        for item in subtitles
    ).strip()

    if not full_text:
        return "unknown", None

    try:
        language = detect(full_text)
    except LangDetectException:
        return "unknown", None

    if language == "ko":
        return "ko", korean_query

    if language == "en":
        return "en", english_query

    return language, None


def get_multilingual_subtitle_candidates(
    korean_query,
    english_query,
    subtitles,
    model,
    top_k=5
):
    candidates = []

    for language, query in [
        ("ko", korean_query),
        ("en", english_query)
    ]:
        results = get_semantic_subtitle_candidates(
            query=query,
            subtitles=subtitles,
            model=model,
            top_k=top_k
        )

        for r in results:
            candidates.append({
                **r,
                "language": language,
                "query_used": query
            })

    return candidates


def deduplicate_multilingual_candidates(
    candidates,
    iou_threshold=0.5,
    start_gap=5.0
):
    # 언어 간 점수를 비교하지 않고
    # 원래 후보 순서를 유지
    selected = []

    for candidate in candidates:
        duplicate = any(
            temporal_iou(candidate, kept) >= iou_threshold
            or (
                abs(
                    candidate["start_time"]
                    - kept["start_time"]
                ) < start_gap
            )
            for kept in selected
        )

        if not duplicate:
            selected.append(candidate)

    return selected


def make_fusion_result(video_id, query, candidate):
    source = candidate["source"]
    is_hybrid = source in ("hybrid", "visual")

    return {
        "video_id": video_id,
        "query": query,
        "start_time": round(float(candidate["start_time"]), 4),
        "end_time": round(float(candidate["end_time"]), 4),
        "score": candidate.get("score") if is_hybrid else None,
        "source": source,
        "hybrid_source": candidate.get("hybrid_source"),
        "visual_score": candidate.get("score") if is_hybrid else None,
        "subtitle_score": (
            candidate.get("subtitle_score")
            if is_hybrid
            else candidate.get("score")
        ),
        "language": candidate.get("language")
    }


def predict_moments_fusion(
    video_id, feature_path, subtitles,
    korean_query, english_query,
    video_duration, subtitle_json_path=None, top_k=5,

    model_type="finetuned"
):
    """
    Korean subtitle-first search.

    1. 한국어 자막이 존재하면 Fine-tuned MiniLM으로 자막 의미 검색
    2. 자막 검색 결과가 있으면 해당 후보들을 반환
    3. 자막이 없거나 검색할 수 없는 경우에만 Moment-DETR visual fallback
    """

    # 1) Subtitle-first
    if subtitles:
        subtitle_candidates = get_semantic_subtitle_candidates(
            query=korean_query,
            subtitles=subtitles,
            model=get_semantic_model(model_type=model_type),
            top_k=top_k,
        )

        if subtitle_candidates:
            results = []

            for candidate in subtitle_candidates:
                candidate = {
                    **candidate,
                    "source": "subtitle",
                    "language": "ko",
                }

                results.append(
                    make_fusion_result(
                        video_id=video_id,
                        query=korean_query,
                        candidate=candidate,
                    )
                )

            return results

    # 2) Visual fallback
    visual_candidates = predict_moments_hybrid(
        video_id=video_id,
        video_feature_path=feature_path,
        query=english_query,
        subtitle_json_path=None,
        video_duration=video_duration,
        top_k=top_k,
    )

    results = []

    for candidate in visual_candidates:
        candidate = {
            **candidate,
            "source": "visual",
            "hybrid_source": candidate.get("source"),
        }

        results.append(
            make_fusion_result(
                video_id=video_id,
                query=korean_query,
                candidate=candidate,
            )
        )

    return results

