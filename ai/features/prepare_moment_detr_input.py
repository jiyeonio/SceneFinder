from pathlib import Path

import torch
import torch.nn.functional as F


# --------------------------------------------------
# 저장된 CLIP feature 경로
# --------------------------------------------------

feature_path = Path(
    "data/features/video_001_clip_features.pt"
)


# --------------------------------------------------
# Feature 불러오기
# --------------------------------------------------

video_features = torch.load(
    feature_path,
    map_location="cpu"
)

print(
    "원본 Feature shape:",
    video_features.shape
)


# --------------------------------------------------
# 1. CLIP feature 정규화
# --------------------------------------------------

video_features = F.normalize(
    video_features,
    dim=-1
)

print(
    "Feature 정규화 완료!"
)


# --------------------------------------------------
# 2. TEF (Temporal Endpoint Feature) 생성
# --------------------------------------------------

num_clips = len(video_features)

tef_start = (
    torch.arange(
        0,
        num_clips,
        dtype=torch.float32
    )
    / num_clips
)

tef_end = (
    tef_start
    + 1.0 / num_clips
)

tef = torch.stack(
    [
        tef_start,
        tef_end
    ],
    dim=1
)

print(
    "TEF shape:",
    tef.shape
)


# --------------------------------------------------
# 3. CLIP feature + TEF 결합
# --------------------------------------------------

moment_detr_features = torch.cat(
    [
        video_features,
        tef
    ],
    dim=1
)

print(
    "최종 Moment-DETR Feature shape:",
    moment_detr_features.shape
)