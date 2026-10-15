from pathlib import Path
import sys
import math
import subprocess

import numpy as np
import torch


# ==================================================
# Paths
# ==================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

MOMENT_DETR_ROOT = (
    PROJECT_ROOT
    / "ai"
    / "vendor"
    / "moment_detr"
)

if str(MOMENT_DETR_ROOT) not in sys.path:
    sys.path.append(str(MOMENT_DETR_ROOT))


from run_on_video.data_utils import ClipFeatureExtractor


# ==================================================
# Config
# ==================================================

CLIP_LEN = 2.0
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

DEFAULT_OUTPUT_DIR = (
    PROJECT_ROOT
    / "data"
    / "features"
)


# ==================================================
# Lazy-loaded CLIP extractor
# ==================================================

_EXTRACTOR = None


def get_feature_extractor():
    """
    CLIP 모델을 최초 1회만 로드하고 이후 재사용한다.
    """

    global _EXTRACTOR

    if _EXTRACTOR is None:
        print(
            f"[AI] Loading video CLIP feature extractor "
            f"on {DEVICE}"
        )

        _EXTRACTOR = ClipFeatureExtractor(
            framerate=1 / CLIP_LEN,
            size=224,
            centercrop=True,
            model_name_or_path="ViT-B/32",
            device=DEVICE
        )

    return _EXTRACTOR



@torch.no_grad()
def _encode_video_fast(
    video_path,
    extractor,
    bsz=60
):
    """
    ffmpeg subprocess로 2초 간격 frame을 직접 추출한 뒤
    기존 CLIP encoder를 사용한다.
    """

    loader = extractor.video_loader

    info = loader._get_video_info(
        str(video_path)
    )

    h = info["height"]
    w = info["width"]

    height, width = loader._get_output_dim(
        h,
        w
    )

    fps = loader.framerate

    duration = info.get(
        "duration",
        -1
    )

    if (
        duration > 0
        and duration < 1 / fps + 0.1
    ):
        fps = 2 / max(
            int(duration),
            1
        )

    filters = [
        f"fps={fps}",
        f"scale={width}:{height}"
    ]

    if loader.centercrop:

        x = int(
            (width - loader.size)
            / 2.0
        )

        y = int(
            (height - loader.size)
            / 2.0
        )

        filters.append(
            f"crop={loader.size}:"
            f"{loader.size}:{x}:{y}"
        )

        out_h = loader.size
        out_w = loader.size

    else:

        out_h = height
        out_w = width

    cmd = [
        "ffmpeg",
        "-v", "error",
        "-i", str(video_path),
        "-vf", ",".join(filters),
        "-f", "rawvideo",
        "-pix_fmt", "rgb24",
        "pipe:1",
    ]

    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True
    )

    frame_size = (
        out_h
        * out_w
        * 3
    )

    if len(result.stdout) % frame_size != 0:
        raise RuntimeError(
            "Invalid raw video byte size"
        )

    video = np.frombuffer(
        result.stdout,
        dtype=np.uint8
    ).reshape(
        -1,
        out_h,
        out_w,
        3
    )

    # writable copy
    video = video.copy()

    video = torch.from_numpy(
        video
    ).float()

    video = video.permute(
        0,
        3,
        1,
        2
    )

    video = extractor.video_preprocessor(
        video
    )

    n_frames = len(video)

    features = []

    for start in range(
        0,
        n_frames,
        bsz
    ):

        batch = video[
            start:start + bsz
        ].to(
            extractor.device
        )

        output = (
            extractor
            .clip_extractor
            .encode_image(batch)
        )

        features.append(
            output
        )

    return torch.cat(
        features,
        dim=0
    )


# ==================================================
# Service function
# ==================================================

def build_feature(
    video_path,
    video_id,
    output_dir=None,
    overwrite=False
):
    """
    MP4 영상에서 Moment-DETR용 CLIP feature를 생성한다.

    Args:
        video_path:
            입력 mp4 파일 경로

        video_id:
            영상 식별자.
            결과 파일명에 사용한다.

        output_dir:
            feature 저장 디렉터리.
            기본값: data/features

        overwrite:
            False이면 이미 feature가 존재할 경우
            다시 생성하지 않고 기존 경로를 반환한다.

    Returns:
        str:
            생성된 .pt feature 파일의 절대 경로

    Output:
        Tensor shape = [T, 512]
        약 2초당 feature 1개
    """

    video_path = Path(video_path).resolve()

    if not video_path.exists():
        raise FileNotFoundError(
            f"Video not found: {video_path}"
        )

    if not video_path.is_file():
        raise ValueError(
            f"video_path is not a file: {video_path}"
        )

    if not video_id:
        raise ValueError(
            "video_id must not be empty"
        )

    if output_dir is None:
        output_dir = DEFAULT_OUTPUT_DIR
    else:
        output_dir = Path(output_dir)

        if not output_dir.is_absolute():
            output_dir = (
                PROJECT_ROOT
                / output_dir
            )

    output_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    output_path = (
        output_dir
        / f"{video_id}_clip_features.pt"
    ).resolve()

    # ----------------------------------------------
    # Cache
    # ----------------------------------------------

    if (
        output_path.exists()
        and not overwrite
    ):
        print(
            f"[AI] Feature cache hit: "
            f"{output_path}"
        )

        return str(output_path)

    # ----------------------------------------------
    # Extract
    # ----------------------------------------------

    print(
        f"[AI] Extracting video feature: "
        f"{video_path}"
    )

    extractor = get_feature_extractor()

    video_features = _encode_video_fast(
        video_path=video_path,
        extractor=extractor
    )

    # 안전하게 CPU tensor로 저장
    if torch.is_tensor(video_features):
        video_features = (
            video_features
            .detach()
            .cpu()
            .float()
        )

    torch.save(
        video_features,
        output_path
    )

    print(
        f"[AI] Feature saved: "
        f"{output_path}"
    )

    print(
        f"[AI] Feature shape: "
        f"{tuple(video_features.shape)}"
    )

    return str(output_path)


# ==================================================
# Standalone test
# ==================================================

if __name__ == "__main__":

    feature_path = build_feature(
        video_path=(
            PROJECT_ROOT
            / "data"
            / "raw"
            / "test_audio.mp4"
        ),
        video_id="video_001",
        overwrite=True
    )

    print(
        f"\nResult: {feature_path}"
    )
