"""영상 자막(Whisper) 생성과 불러오기.

저장 위치: data/processed/subtitles/{유튜브ID}.json  (git에 올라가지 않는 폴더)
파일이 없으면 '자막 없음'으로 보고, 검색은 영상(Moment-DETR) 방식으로 넘어갑니다.
"""
import json
import logging
import os
import re
from pathlib import Path

logger = logging.getLogger("uvicorn.error")

ROOT = Path(__file__).resolve().parents[2]
SUBTITLE_DIR = ROOT / "data" / "processed" / "subtitles"

WHISPER_MODEL_SIZE = os.getenv("WHISPER_MODEL_SIZE", "small")
MIN_SUBTITLE_SEGMENTS = 3   # 이보다 적으면 말이 거의 없는 영상으로 봄
MIN_SUBTITLE_CHARS = 30

HANGUL_RE = re.compile(r"[가-힣]")

_model = None
_model_device = None
_force_cpu = False


def subtitle_path(youtube_video_id: str) -> Path:
    return SUBTITLE_DIR / f"{youtube_video_id}.json"


def _add_torch_dll_dir() -> None:
    """Windows에서 torch가 가진 CUDA 라이브러리를 Whisper도 찾을 수 있게 합니다."""
    if os.name != "nt":
        return
    try:
        import torch

        os.add_dll_directory(str(Path(torch.__file__).resolve().parent / "lib"))
    except Exception:
        pass


def _get_model(device: str):
    global _model, _model_device
    if _model is not None and _model_device == device:
        return _model

    _add_torch_dll_dir()
    from faster_whisper import WhisperModel

    if device == "cuda":
        model = WhisperModel(WHISPER_MODEL_SIZE, device="cuda", compute_type="float16")
    else:
        model = WhisperModel(WHISPER_MODEL_SIZE, device="cpu", compute_type="int8")
    _model, _model_device = model, device
    return model


def _transcribe(video_path: str):
    """GPU로 먼저 시도하고, 안 되면 CPU로 넘어갑니다. (items, 언어, 확률)"""
    global _force_cpu
    devices = ["cpu"] if _force_cpu else ["cuda", "cpu"]

    for device in devices:
        try:
            model = _get_model(device)
            segments, info = model.transcribe(
                video_path,
                beam_size=5,
                vad_filter=True,
                condition_on_previous_text=False,
            )
            items = [
                {
                    "start_time": round(float(s.start), 2),
                    "end_time": round(float(s.end), 2),
                    "text": s.text.strip(),
                }
                for s in segments
                if s.text.strip()
            ]
            return items, info.language, float(info.language_probability)
        except Exception as e:
            if device == "cuda":
                logger.warning("Whisper GPU 사용 실패, CPU로 전환합니다: %s", e)
                _force_cpu = True
                continue
            raise


def transcribe_video(video_path: str, youtube_video_id: str) -> str:
    """영상에서 자막을 만들어 저장하고, 저장 경로(레포 기준 상대경로)를 돌려줍니다."""
    SUBTITLE_DIR.mkdir(parents=True, exist_ok=True)

    items, language, probability = _transcribe(str(video_path))

    total_chars = sum(len(i["text"]) for i in items)
    if len(items) < MIN_SUBTITLE_SEGMENTS or total_chars < MIN_SUBTITLE_CHARS:
        items = []  # 말이 거의 없는 영상 → 자막 검색 대신 영상 검색

    out = subtitle_path(youtube_video_id)
    out.write_text(
        json.dumps(
            {
                "language": language,
                "language_probability": round(probability, 4),
                "segments": items,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return out.relative_to(ROOT).as_posix()


def load_subtitles(youtube_video_id: str):
    """(자막 리스트, 언어) 를 돌려줍니다. 자막이 없으면 ([], None).

    파일은 {"language":..,"segments":[..]} 형식이거나,
    AI팀 샘플처럼 [{start_time, end_time, text}, ...] 리스트여도 됩니다.
    """
    path = subtitle_path(youtube_video_id)
    if not path.exists():
        return [], None

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return [], None

    if isinstance(data, list):
        segments = data
        text = "".join(str(s.get("text", "")) for s in segments).replace(" ", "")
        ratio = len(HANGUL_RE.findall(text)) / len(text) if text else 0
        language = "ko" if ratio > 0.3 else "en"
    else:
        segments = data.get("segments", [])
        language = data.get("language")

    segments = [
        s for s in segments
        if isinstance(s, dict) and all(k in s for k in ("start_time", "end_time", "text"))
    ]
    if not segments:
        return [], None
    return segments, language