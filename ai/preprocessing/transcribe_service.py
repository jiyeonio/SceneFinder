"""
SceneFinder Whisper transcription service.

Converts uploaded video speech into timestamped subtitle JSON.
Existing subtitle files are reused without overwriting them.
"""

import json
from pathlib import Path
from functools import lru_cache

from faster_whisper import WhisperModel


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"


@lru_cache(maxsize=1)
def get_whisper_model():
    return WhisperModel(
        "small",
        device="cpu",
        compute_type="int8"
    )


def transcribe_video(video_path, video_id):
    """
    Generate or reuse subtitles for a video.

    Returns an absolute path to:
    data/processed/{video_id}/subtitles.json
    """

    video_path = Path(video_path).resolve()

    if not video_path.is_file():
        raise FileNotFoundError(
            f"Input video not found: {video_path}"
        )

    video_id = str(video_id)

    if (
        not video_id
        or video_id in {".", ".."}
        or Path(video_id).name != video_id
        or "/" in video_id
        or "\\" in video_id
    ):
        raise ValueError(
            f"Invalid video_id: {video_id!r}"
        )

    output_path = (
        PROCESSED_DIR
        / video_id
        / "subtitles.json"
    )

    if output_path.is_file():
        return str(output_path)

    segments, info = get_whisper_model().transcribe(
        str(video_path),
        beam_size=5
    )

    subtitles = [
        {
            "start_time": round(s.start, 2),
            "end_time": round(s.end, 2),
            "text": s.text.strip()
        }
        for s in segments
    ]

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with output_path.open("x", encoding="utf-8") as f:
        json.dump(
            subtitles,
            f,
            ensure_ascii=False,
            indent=2
        )

    return str(output_path)
