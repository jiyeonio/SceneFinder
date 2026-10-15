import os
import cv2
from pathlib import Path


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

segment_length = 10
overlap = 5


cap = cv2.VideoCapture(
    str(video_path)
)

if not cap.isOpened():
    print("영상 파일을 열 수 없습니다.")
    exit()


fps = cap.get(cv2.CAP_PROP_FPS)
frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)

duration = frame_count / fps if fps > 0 else 0

cap.release()


step = segment_length - overlap

segments = []

start_time = 0
segment_number = 1


while start_time < duration:

    end_time = min(
        start_time + segment_length,
        duration
    )

    segment = {
        "segment_id": (
            f"{video_id}_seg_{segment_number:04d}"
        ),
        "start_time": round(start_time, 2),
        "end_time": round(end_time, 2)
    }

    segments.append(segment)

    start_time += step
    segment_number += 1


print("=== Segment Result ===")

for segment in segments:
    print(segment)

print()
print(
    f"Total Segments: {len(segments)}"
)