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
frames_per_segment = 3

output_root = (
    Path("data/processed")
    / video_id
    / "frames"
)


# --------------------------------------------------
# 영상 열기
# --------------------------------------------------

cap = cv2.VideoCapture(
    str(video_path)
)

if not cap.isOpened():
    print("영상 파일을 열 수 없습니다.")
    exit()


fps = cap.get(cv2.CAP_PROP_FPS)
frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)

duration = frame_count / fps if fps > 0 else 0

print("=== Frame Extraction ===")
print(f"Duration: {duration:.2f} seconds")


# --------------------------------------------------
# Segment 생성
# --------------------------------------------------

step = segment_length - overlap

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

    segment_dir = (
        output_root
        / segment_id
    )

    segment_dir.mkdir(
        parents=True,
        exist_ok=True
    )


    # ----------------------------------------------
    # Segment 안에서 균등하게 3개 시점 선택
    # ----------------------------------------------

    segment_duration = (
        end_time - start_time
    )

    sample_times = []

    for i in range(frames_per_segment):

        ratio = (
            (i + 1)
            / (frames_per_segment + 1)
        )

        sample_time = (
            start_time
            + segment_duration * ratio
        )

        sample_times.append(
            sample_time
        )


    # ----------------------------------------------
    # Frame 추출
    # ----------------------------------------------

    for frame_number, sample_time in enumerate(
        sample_times,
        start=1
    ):

        cap.set(
            cv2.CAP_PROP_POS_MSEC,
            sample_time * 1000
        )

        success, frame = cap.read()

        if not success:

            print(
                f"[실패] {segment_id} / "
                f"{sample_time:.2f}초"
            )

            continue


        # ------------------------------------------
        # 4K 영상이므로 테스트용으로 크기 축소
        # ------------------------------------------

        height, width = frame.shape[:2]

        target_width = 640

        if width > target_width:

            ratio = (
                target_width / width
            )

            new_height = int(
                height * ratio
            )

            frame = cv2.resize(
                frame,
                (
                    target_width,
                    new_height
                )
            )


        # ------------------------------------------
        # 이미지 저장
        # ------------------------------------------

        output_path = (
            segment_dir
            / f"frame_{frame_number:03d}.jpg"
        )

        cv2.imwrite(
            str(output_path),
            frame
        )


    print(
        f"{segment_id}: "
        f"{start_time:.2f} ~ "
        f"{end_time:.2f}초 "
        f"→ {len(sample_times)} frames"
    )


    start_time += step
    segment_number += 1


cap.release()

print()
print("Frame extraction complete!")
print(f"저장 위치: {output_root}")