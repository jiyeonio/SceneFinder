import argparse
import os
import subprocess
import sys
from pathlib import Path


# --------------------------------------------------
# 실행할 때 영상 / 자막 정보 입력받기
# --------------------------------------------------

parser = argparse.ArgumentParser(
    description="SceneFinder 영상 전처리 파이프라인"
)

parser.add_argument(
    "--video",
    required=True,
    help="원본 영상 경로"
)

parser.add_argument(
    "--video-id",
    required=True,
    help="영상 ID"
)

parser.add_argument(
    "--subtitle",
    required=True,
    help="VTT 자막 파일 경로"
)

args = parser.parse_args()


video_path = Path(args.video)
video_id = args.video_id
subtitle_path = Path(args.subtitle)


# --------------------------------------------------
# 입력 파일 존재 여부 확인
# --------------------------------------------------

if not video_path.exists():

    print(
        f"[오류] 영상 파일을 찾을 수 없습니다: "
        f"{video_path}"
    )

    sys.exit(1)


if not subtitle_path.exists():

    print(
        f"[오류] 자막 파일을 찾을 수 없습니다: "
        f"{subtitle_path}"
    )

    sys.exit(1)


# --------------------------------------------------
# 다른 preprocessing 파일에 전달할 값
# --------------------------------------------------

env = os.environ.copy()

env["SCENEFINDER_VIDEO_PATH"] = str(video_path)
env["SCENEFINDER_VIDEO_ID"] = video_id
env["SCENEFINDER_SUBTITLE_PATH"] = str(subtitle_path)


# --------------------------------------------------
# 실행할 preprocessing 파일
# --------------------------------------------------

scripts = [
    "ai/preprocessing/video_metadata.py",
    "ai/preprocessing/segment_video.py",
    "ai/preprocessing/extract_frames.py",
    "ai/preprocessing/parse_subtitle.py",
    "ai/preprocessing/align_transcript.py",
    "ai/preprocessing/build_video_data.py",
]


output_path = Path(
    f"data/processed/{video_id}/video_data.json"
)


# --------------------------------------------------
# Pipeline 시작
# --------------------------------------------------

print("====================================")
print(" Video Preprocessing Pipeline Start")
print("====================================")

print()
print(f"Video: {video_path}")
print(f"Video ID: {video_id}")
print(f"Subtitle: {subtitle_path}")
print()


for script in scripts:

    print(f"[실행] {script}")

    result = subprocess.run(
        [sys.executable, script],
        env=env
    )

    if result.returncode != 0:

        print()
        print(f"[실패] {script}")
        print("Pipeline을 중단합니다.")

        sys.exit(1)

    print(f"[완료] {script}")
    print()


print("====================================")
print(" Video Preprocessing Pipeline Done!")
print("====================================")

print()
print(
    f"최종 결과: {output_path}"
)