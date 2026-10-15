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

subtitle_path = Path(
    f"data/processed/{video_id}/subtitle.json"
)

output_path = Path(
    f"data/processed/{video_id}/segments_with_subtitles.json"
)

segment_length = 10
overlap = 5

metadata = get_video_metadata(
    str(video_path)
)

duration = metadata["duration"]

# --------------------------------------------------
# 자막 불러오기
# --------------------------------------------------

with open(
    subtitle_path,
    "r",
    encoding="utf-8"
) as f:
    subtitles = json.load(f)


# --------------------------------------------------
# Segment 생성
# --------------------------------------------------

step = segment_length - overlap

segments = []

start_time = 0
segment_number = 1


while start_time < duration:

    end_time = min(
        start_time + segment_length,
        duration
    )

    segment_id = (
        f"{video_id}_seg_{segment_number:04d}"
    )

    frame_folder = (
        f"{video_id}_seg_{segment_number:04d}"
    )


    # --------------------------------------------------
    # 현재 Segment와 겹치는 자막 찾기
    # --------------------------------------------------

    matched_texts = []

    for subtitle in subtitles:

        subtitle_start = subtitle["start_time"]
        subtitle_end = subtitle["end_time"]

        # 자막 시간과 segment 시간이 겹치면 포함
        if (
            subtitle_end > start_time
            and subtitle_start < end_time
        ):
            matched_texts.append(
                subtitle["text"]
            )


    transcript = " ".join(
        matched_texts
    ).strip()


    # --------------------------------------------------
    # Segment 데이터 생성
    # --------------------------------------------------

    segment = {
        "video_id": video_id,

        "segment_id": segment_id,

        "start_time": round(
            start_time,
            2
        ),

        "end_time": round(
            end_time,
            2
        ),

        "transcript": transcript,

        "frame_dir": (
            f"data/processed/"
            f"{video_id}/frames/"
            f"{frame_folder}/"
        )
    }


    segments.append(segment)

    start_time += step
    segment_number += 1


# --------------------------------------------------
# JSON 저장
# --------------------------------------------------

with open(
    output_path,
    "w",
    encoding="utf-8"
) as f:

    json.dump(
        segments,
        f,
        ensure_ascii=False,
        indent=2
    )


# --------------------------------------------------
# 결과 출력
# --------------------------------------------------

print(
    "=== Segment + Subtitle Result ==="
)


for segment in segments:

    print()

    print(
        f"{segment['segment_id']} "
        f"[{segment['start_time']:.2f} ~ "
        f"{segment['end_time']:.2f}]"
    )

    print(
        f"Transcript: "
        f"{segment['transcript']}"
    )

    print(
        f"Frame Dir: "
        f"{segment['frame_dir']}"
    )


print()

print(
    f"총 Segment 개수: "
    f"{len(segments)}"
)

print(
    f"저장 위치: "
    f"{output_path}"
)