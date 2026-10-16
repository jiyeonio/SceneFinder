"""번역 방식별 영상 검색 비교 + 자막 검색 실험.

방식
  (a) 현재 번역기(NLLB, backend/services/translate.py) → Moment-DETR 1위 구간
  (b) Helsinki-NLP/opus-mt-ko-en 번역 → Moment-DETR 1위 구간
  (c) 번역 없이 다국어 CLIP(clip-ViT-B-32-multilingual-v1)으로 2초 단위 프레임 feature와 직접 비교
  (d) 자막 검색: 서비스와 같은 Whisper 자막 + Fine-tuned MiniLM 1위 구간 (서비스의 구간 보정 적용)

실행 (프로젝트 루트에서, 가상환경과 backend/.env 준비 후):
    python ai/experiments/translation_compare/run.py [--out 출력폴더] [--queries 라벨링.json]
    python ai/experiments/translation_compare/make_report.py [--results 출력폴더/results.json]

영상 feature, 자막, 결과 JSON은 --out 폴더(기본: 시스템 임시 폴더)에 저장하고 저장소에는 쓰지 않습니다.
--queries를 주면 queries.py 대신 라벨링 도구(tools/labeler)가 저장한 JSON의 질의·정답 구간·영상을 씁니다.
feature·자막 캐시 파일 이름은 영상 키(bench_<키>)라, 같은 --out 폴더에서 같은 키를 다른 영상에 쓰면 안 됩니다.
결과 요약(results.json의 summary)은 전체·S·V, V의 화면 글자 있음/없음/미표시, 질의 source별로 나눠 집계합니다.
"""
import argparse
import json
import os
import random
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))
os.chdir(ROOT)

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / "backend" / ".env")

import torch  # noqa: E402
import torch.nn.functional as F  # noqa: E402

import query_set  # noqa: E402
import summary  # noqa: E402

MULTI_CLIP_DIR = ROOT / "ai/experiments/korean_ai_handoff/model_assets/multilingual_clip"
MULTI_CLIP_HF = "sentence-transformers/clip-ViT-B-32-multilingual-v1"  # 로컬 폴더가 없으면 HuggingFace에서 받음
OPUS = "Helsinki-NLP/opus-mt-ko-en"
RANDOM_SAMPLES = 100
RANDOM_SEED = 0
# 서비스의 자막 구간 보정과 같은 값 (backend/services/search_api.py의 _widen_subtitle)
SUBTITLE_PAD_BEFORE = float(os.getenv("SUBTITLE_PAD_BEFORE", "2.0"))
SUBTITLE_MIN_LEN = float(os.getenv("SUBTITLE_MIN_LEN", "6.0"))
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
SUMMARY_LABELS = {"a": "(a) NLLB+Moment-DETR", "b": "(b) opus-mt+Moment-DETR", "c": "(c) 다국어 CLIP",
                  "d": "(d) 자막 검색", "d_raw": "(d) 자막 검색·보정 전", "random": "무작위 기준선"}


def duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True,
    )
    return float(out.stdout.strip())


def has_audio(path: Path) -> bool:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True,
    )
    return bool(out.stdout.strip())


def iou(a, b) -> float:
    inter = max(0.0, min(a[1], b[1]) - max(a[0], b[0]))
    union = max(a[1], b[1]) - min(a[0], b[0])
    return inter / union if union > 0 else 0.0


def best_iou(seg, gts) -> float:
    """정답이 여러 구간이면 가장 높은 IoU."""
    return max(iou(seg, g) for g in gts)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=os.path.join(tempfile.gettempdir(), "translation_compare"),
                        help="feature·자막·결과 JSON을 저장할 폴더 (저장소 밖 권장)")
    parser.add_argument("--queries", default=None, help="라벨링 도구가 저장한 질의 JSON (없으면 queries.py)")
    args = parser.parse_args()
    qs = query_set.load(args.queries)
    QUERIES = qs.queries
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    print("질의:", qs.source, f"({len(QUERIES)}개, 영상 {len(qs.video_keys)}개)")
    print("출력 폴더:", out)

    # ---------- 영상 feature (서비스와 같은 build_feature, 출력은 out 폴더) ----------
    from ai.features.moment_detr_features import build_feature

    videos = {k: qs.video_path(k) for k in qs.video_keys}
    feats = {k: build_feature(str(p), f"bench_{k}", output_dir=str(out), overwrite=False) for k, p in videos.items()}
    durs = {k: duration(p) for k, p in videos.items()}

    # ---------- (d) 자막: 서비스와 같은 Whisper 설정 ----------
    from services import subtitles as st

    subs = {}
    for k, p in videos.items():
        cache = out / f"bench_{k}_subtitles.json"
        if cache.exists():
            subs[k] = json.loads(cache.read_text(encoding="utf-8"))
        elif not has_audio(p):  # 오디오 트랙이 없는 영상: 자막 없음으로 처리 (Whisper 디코딩 오류 방지)
            subs[k] = {"language": None, "segments": []}
            cache.write_text(json.dumps(subs[k], ensure_ascii=False, indent=1), encoding="utf-8")
        else:
            items, language, _ = st._transcribe(str(p))
            subs[k] = {"language": language, "segments": items}
            cache.write_text(json.dumps(subs[k], ensure_ascii=False, indent=1), encoding="utf-8")

    from ai.features.fusion_search import get_semantic_model, get_semantic_subtitle_candidates

    minilm = get_semantic_model(model_type="finetuned")

    def subtitle_top1(key, ko):
        segments = subs[key]["segments"]
        if not segments:
            return None
        top = get_semantic_subtitle_candidates(query=ko, subtitles=segments, model=minilm, top_k=5)[0]
        raw = (float(top["start_time"]), float(top["end_time"]))
        start = max(0.0, raw[0] - SUBTITLE_PAD_BEFORE)
        widened = (start, max(raw[1], start + SUBTITLE_MIN_LEN))
        return raw, widened, float(top["score"]), top["text"]

    # ---------- (e) VLM 장면 설명문 검색: captions.py가 만든 captions_<variant>.json이 있으면 평가 ----------
    # 설명문을 자막처럼 MiniLM으로 검색 (말 기준인 자막 구간 보정은 적용하지 않음)
    captions = {}
    for path in sorted(out.glob("captions_*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        captions[data["meta"]["variant"]] = data

    def caption_eval(variant, key, ko, gts):
        segments = captions[variant]["videos"][key]
        ranked = get_semantic_subtitle_candidates(query=ko, subtitles=segments, model=minilm, top_k=10**6)
        top = ranked[0]
        seg = (float(top["start_time"]), float(top["end_time"]))
        # 틀린 이유 분석용: 정답과 겹치는(IoU ≥ 0.3) 후보 중 가장 높은 순위, 정답 구간에 걸친 설명문
        gt_rank, gt_hit = None, None
        for rank, cand in enumerate(ranked, 1):
            if best_iou((float(cand["start_time"]), float(cand["end_time"])), gts) >= 0.3:
                gt_rank, gt_hit = rank, cand
                break
        in_gt = [s["text"] for s in segments
                 if any(min(s["end_time"], b) - max(s["start_time"], a) > 0 for a, b in gts)]
        return {"seg": seg, "score": float(top["score"]), "iou": best_iou(seg, gts), "text": top["text"],
                "gt_rank": gt_rank, "gt_rank_of": len(ranked), "gt_best_score": float(gt_hit["score"]) if gt_hit else None,
                "gt_best_text": gt_hit["text"] if gt_hit else None, "gt_captions": in_gt}

    # ---------- (a) 현재 번역기 / (b) opus-mt ----------
    from services.translate import MODEL_NAME as NLLB_NAME, to_english
    from transformers import MarianMTModel, MarianTokenizer

    opus_tok = MarianTokenizer.from_pretrained(OPUS)
    opus_model = MarianMTModel.from_pretrained(OPUS).to(DEVICE).eval()

    @torch.no_grad()
    def opus_en(text):
        batch = opus_tok([text], return_tensors="pt").to(DEVICE)
        return opus_tok.decode(opus_model.generate(**batch, max_new_tokens=64)[0], skip_special_tokens=True)

    # ---------- Moment-DETR (서비스와 같은 함수) ----------
    from ai.features.run_moment_detr_inference import (
        CLIP_LEN, VISUAL_TOP_K, _make_contiguous_clusters, _smooth_scores, predict_moments_hybrid)

    def detr_top1(key, en):
        r = predict_moments_hybrid(video_id=f"bench_{key}", video_feature_path=feats[key], query=en, top_k=5)
        return (float(r[0]["start_time"]), float(r[0]["end_time"])), float(r[0]["score"])

    # ---------- (c) 다국어 CLIP ----------
    # 구간 선택은 저장소의 _refine_visual_start와 같은 규칙을 영상 전체에 적용:
    # 유사도 평활화 → 상위 VISUAL_TOP_K개 bin → 연속 구간 중 (길이, 평균 유사도)가 가장 큰 것
    from sentence_transformers import SentenceTransformer

    mclip = SentenceTransformer(str(MULTI_CLIP_DIR) if MULTI_CLIP_DIR.is_dir() else MULTI_CLIP_HF, device=DEVICE)

    @torch.no_grad()
    def mclip_top1(key, ko):
        vf = F.normalize(torch.load(feats[key], map_location="cpu").float(), dim=-1)
        q = F.normalize(torch.tensor(mclip.encode([ko]))[0].float(), dim=-1)
        smoothed = _smooth_scores(vf @ q)
        top = torch.topk(smoothed, k=min(VISUAL_TOP_K, len(smoothed))).indices.tolist()
        multi = [c for c in _make_contiguous_clusters(top) if len(c) >= 2]
        best = max(multi, key=lambda c: (len(c), float(smoothed[c].mean()))) if multi else [int(torch.argmax(smoothed))]
        seg = (min(best) * CLIP_LEN, min((max(best) + 1) * CLIP_LEN, durs[key]))
        return (float(seg[0]), float(seg[1])), float(smoothed[best].mean())

    # ---------- 무작위 기준선: 영상별 정답 평균 길이의 구간을 무작위 위치에 RANDOM_SAMPLES번 ----------
    rng = random.Random(RANDOM_SEED)
    gt_len = {}
    for k in videos:
        spans = [g for (_, v, _, _, gts) in QUERIES if v == k for g in gts]
        gt_len[k] = sum(b - a for a, b in spans) / len(spans)

    def random_baseline(key, gts):
        length, dur = gt_len[key], durs[key]
        ious = []
        for _ in range(RANDOM_SAMPLES):
            s = rng.uniform(0, max(0.0, dur - length))
            ious.append(best_iou((s, s + length), gts))
        return {"mean_iou": sum(ious) / len(ious),
                "hit30": sum(i >= 0.3 for i in ious) / len(ious),
                "hit50": sum(i >= 0.5 for i in ious) / len(ious)}

    rows = []
    for num, key, typ, ko, gts in QUERIES:
        en_a, en_b = to_english(ko), opus_en(ko)
        seg_a, sc_a = detr_top1(key, en_a)
        seg_b, sc_b = detr_top1(key, en_b)
        seg_c, sc_c = mclip_top1(key, ko)
        sub = subtitle_top1(key, ko)
        row = {
            "num": num, "video": key, "type": typ, "query": ko, "gt": gts, "en_a": en_a, "en_b": en_b,
            "a": {"seg": seg_a, "score": sc_a, "iou": best_iou(seg_a, gts)},
            "b": {"seg": seg_b, "score": sc_b, "iou": best_iou(seg_b, gts)},
            "c": {"seg": seg_c, "score": sc_c, "iou": best_iou(seg_c, gts)},
            "random": random_baseline(key, gts),
        }
        if sub:
            raw, widened, score, text = sub
            row["d"] = {"seg": widened, "score": score, "iou": best_iou(widened, gts), "text": text,
                        "raw_seg": raw, "raw_iou": best_iou(raw, gts)}
        for variant in captions:
            row[f"e_{variant}"] = caption_eval(variant, key, ko, gts)
        rows.append(summary.annotate(row, qs))
        print(f"#{num:2d} {typ} a={row['a']['iou']:.2f} b={row['b']['iou']:.2f} c={row['c']['iou']:.2f} "
              f"d={row.get('d', {}).get('iou', float('nan')):.2f}", flush=True)

    meta = {
        "queries_source": qs.source, "video_names": {k: qs.name(k) for k in videos},
        "nllb": NLLB_NAME, "opus": OPUS, "mclip": "sentence-transformers/clip-ViT-B-32-multilingual-v1",
        "whisper": st.WHISPER_MODEL_SIZE, "minilm": "fine-tuned MiniLM (SCENEFINDER_MINILM_MODEL_PATH)",
        "subtitle_pad_before": SUBTITLE_PAD_BEFORE, "subtitle_min_len": SUBTITLE_MIN_LEN,
        "subtitle_segments": {k: len(v["segments"]) for k, v in subs.items()},
        "subtitle_language": {k: v["language"] for k, v in subs.items()},
        "captions": {v: d["meta"] for v, d in captions.items()},
        "durations": durs, "gt_mean_len": gt_len, "random_samples": RANDOM_SAMPLES, "random_seed": RANDOM_SEED,
        "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu",
    }
    # S/V, V의 화면 글자 유무, source별 집계 (자막이 없어 (d) 결과가 없는 질의는 IoU 0)
    methods = {m: summary.by_iou(lambda r, m=m: r[m]["iou"]) for m in ("a", "b", "c")}
    methods["d"] = summary.by_iou(lambda r: r.get("d", {}).get("iou"))
    methods["d_raw"] = summary.by_iou(lambda r: r.get("d", {}).get("raw_iou"))
    for v in captions:
        methods[f"e_{v}"] = summary.by_iou(lambda r, v=v: r.get(f"e_{v}", {}).get("iou"))
    methods["random"] = lambda r: (r["random"]["mean_iou"], r["random"]["hit30"], r["random"]["hit50"])
    result_summary = summary.summarize(rows, methods)
    print(summary.format_table(result_summary, SUMMARY_LABELS))

    path = out / "results.json"
    path.write_text(json.dumps({"meta": meta, "summary": result_summary, "rows": rows}, ensure_ascii=False, indent=1),
                    encoding="utf-8")
    print("저장:", path)


if __name__ == "__main__":
    main()
