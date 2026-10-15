import os
import cv2


def get_video_metadata(video_path):

    cap = cv2.VideoCapture(video_path)

    if not cap.isOpened():
        raise FileNotFoundError(
            f"영상 파일을 열 수 없습니다: {video_path}"
        )

    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
    height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)

    duration = frame_count / fps if fps > 0 else 0

    cap.release()

    metadata = {
        "fps": fps,
        "frame_count": int(frame_count),
        "width": int(width),
        "height": int(height),
        "duration": duration
    }

    return metadata


if __name__ == "__main__":

    video_path = os.getenv(
        "SCENEFINDER_VIDEO_PATH",
        "data/raw/test_audio.mp4"
    )

    metadata = get_video_metadata(video_path)

    print("=== Video Metadata ===")
    print(f"FPS: {metadata['fps']}")
    print(f"Frame Count: {metadata['frame_count']}")
    print(
        f"Resolution: "
        f"{metadata['width']} x {metadata['height']}"
    )
    print(
        f"Duration: "
        f"{metadata['duration']:.2f} seconds"
    )