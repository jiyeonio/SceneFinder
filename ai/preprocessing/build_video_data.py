import os
import json
from pathlib import Path

from video_metadata import get_video_metadata


video_path = Path(
    os.getenv(
        "SCENEFINDER_VIDEO_PATH",
        "data/raw/test_audio.mp4"
    )
)

video_id = os.getenv(
    "SCENEFINDER_VIDEO_ID",
    "video_001"
)

segments_path = Path(
    f"data/processed/{video_id}/segments_with_subtitles.json"
)

output_path = Path(
    f"data/processed/{video_id}/video_data.json"
)


# --------------------------------------------------
# 영상 metadata 읽기
# --------------------------------------------------

metadata = get_video_metadata(
    str(video_path)
)

fps = metadata["fps"]
width = metadata["width"]
height = metadata["height"]
duration = metadata["duration"]


# --------------------------------------------------
# segment + subtitle 데이터 불러오기
# --------------------------------------------------

with open(
    segments_path,
    "r",
    encoding="utf-8"
) as f:

    segments = json.load(f)


# --------------------------------------------------
# 최종 AI 입력 데이터 구성
# --------------------------------------------------

video_data = {
    "video_id": video_id,
    "duration": round(duration, 2),
    "fps": round(fps, 2),
    "width": int(width),
    "height": int(height),
    "segments": segments
}


# --------------------------------------------------
# JSON 저장
# --------------------------------------------------

with open(
    output_path,
    "w",
    encoding="utf-8"
) as f:

    json.dump(
        video_data,
        f,
        ensure_ascii=False,
        indent=2
    )


# --------------------------------------------------
# 결과 확인
# --------------------------------------------------

print("=== Final Video Data ===")

print(f"Video ID: {video_id}")
print(f"Duration: {duration:.2f} seconds")
print(f"FPS: {fps:.2f}")
print(
    f"Resolution: "
    f"{int(width)} x {int(height)}"
)

print(
    f"Total Segments: "
    f"{len(segments)}"
)

print()

print(
    f"저장 위치: "
    f"{output_path}"
)