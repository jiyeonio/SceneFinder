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

WHISPER_MODEL_SIZE = os.getenv("WHISPER_MODEL_SIZE", "large-v3-turbo")
MIN_SUBTITLE_SEGMENTS = 3   # 이보다 적으면 말이 거의 없는 영상으로 봄
MIN_SUBTITLE_CHARS = 30

HANGUL_RE = re.compile(r"[가-힣]")

_model = None
_model_device = None
_force_cpu = False


def subtitle_path(youtube_video_id: str) -> Path:
    return SUBTITLE_DIR / f"{youtube_video_id}.json"


def _load_torch_cuda_libs() -> bool:
    """torch가 가진 CUDA 라이브러리(cuBLAS 등)를 먼저 불러와 Whisper(ctranslate2)가 GPU를 쓸 수 있게 합니다.

    Linux에서는 torch를 import해야 libcublas.so.12가 프로세스에 올라옵니다. 이것 없이 Whisper만 쓰면
    GPU 초기화가 실패해 CPU로 넘어갑니다. Windows에서는 torch의 lib 폴더를 DLL 검색 경로에 추가합니다.
    GPU를 쓸 수 있으면 True.
    """
    try:
        import torch
    except Exception as e:
        logger.warning("torch를 불러오지 못해 Whisper가 GPU를 못 쓸 수 있습니다: %s", e)
        return False
    if os.name == "nt":
        try:
            os.add_dll_directory(str(Path(torch.__file__).resolve().parent / "lib"))
        except Exception:
            pass
    if not torch.cuda.is_available():
        logger.warning("GPU(CUDA)를 찾지 못했습니다. Whisper 자막 생성을 CPU로 실행합니다 (느림).")
        return False
    return True


def _get_model(device: str):
    global _model, _model_device
    if _model is not None and _model_device == device:
        return _model

    from faster_whisper import WhisperModel

    if device == "cuda":
        model = WhisperModel(WHISPER_MODEL_SIZE, device="cuda", compute_type="float16")
    else:
        model = WhisperModel(WHISPER_MODEL_SIZE, device="cpu", compute_type="int8")
    logger.info("Whisper %s 모델을 %s에 올렸습니다", WHISPER_MODEL_SIZE, device.upper())
    _model, _model_device = model, device
    return model


def _transcribe(video_path: str):
    """GPU로 먼저 시도하고, 안 되면 CPU로 넘어갑니다. (items, 언어, 확률)"""
    global _force_cpu
    if not _force_cpu and _model is None and not _load_torch_cuda_libs():
        _force_cpu = True
    devices = ["cpu"] if _force_cpu else ["cuda", "cpu"]
    freed = False

    while devices:
        device = devices.pop(0)
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
            if device == "cuda" and "out of memory" in str(e).lower():
                # GPU 메모리 부족은 잠깐일 수 있음: 설명문 모델을 내릴 수 있으면 내리고 GPU로 한 번 더,
                # 그래도 안 되면 이번 영상만 CPU (다음 영상은 다시 GPU부터)
                if not freed:
                    freed = True
                    from . import captions
                    if captions.release_gpu():
                        logger.warning("Whisper GPU 메모리 부족, 설명문 모델을 내리고 다시 시도합니다: %s", e)
                        devices.insert(0, "cuda")
                        continue
                logger.warning("Whisper GPU 메모리 부족, 이번 영상만 CPU로 만듭니다 (느림): %s", e)
                continue
            if device == "cuda":
                logger.warning("Whisper GPU 사용 실패, CPU로 전환합니다 (이후 자막 생성은 모두 CPU, 느림): %s", e)
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