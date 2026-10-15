from pathlib import Path
import torch


feature_path = Path(
    "data/features/video_001_clip_features.pt"
)


# --------------------------------------------------
# 파일 존재 확인
# --------------------------------------------------

if not feature_path.exists():
    raise FileNotFoundError(
        f"Feature 파일을 찾을 수 없습니다: {feature_path}"
    )


# --------------------------------------------------
# Feature 불러오기
# --------------------------------------------------

video_features = torch.load(
    feature_path,
    map_location="cpu"
)


# --------------------------------------------------
# 확인
# --------------------------------------------------

print("Feature 불러오기 성공!")

print(
    "Feature shape:",
    video_features.shape
)

print(
    "Data type:",
    video_features.dtype
)

print(
    "Device:",
    video_features.device
)