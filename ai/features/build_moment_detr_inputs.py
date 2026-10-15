from pathlib import Path
import sys

import torch
import torch.nn.functional as F


# --------------------------------------------------
# Moment-DETR repository 경로
# --------------------------------------------------

MOMENT_DETR_ROOT = Path(
    "ai/external/moment_detr"
)

sys.path.append(
    str(MOMENT_DETR_ROOT.resolve())
)


# --------------------------------------------------
# Moment-DETR utility import
# --------------------------------------------------

from run_on_video.data_utils import (
    ClipFeatureExtractor
)

from utils.tensor_utils import (
    pad_sequences_1d
)


# --------------------------------------------------
# 설정
# --------------------------------------------------

video_feature_path = Path(
    "data/features/video_001_clip_features.pt"
)

query = (
    "the steak is flipped "
    "while cooking in the pan"
)


# --------------------------------------------------
# 1. 저장된 Video Feature 불러오기
# --------------------------------------------------

video_feats = torch.load(
    video_feature_path,
    map_location="cpu"
)

video_feats = F.normalize(
    video_feats,
    dim=-1,
    eps=1e-5
)

n_frames = len(video_feats)


# --------------------------------------------------
# 2. TEF 추가
# --------------------------------------------------

tef_st = (
    torch.arange(
        0,
        n_frames,
        dtype=torch.float32
    )
    / n_frames
)

tef_ed = (
    tef_st
    + 1.0 / n_frames
)

tef = torch.stack(
    [
        tef_st,
        tef_ed
    ],
    dim=1
)

video_feats = torch.cat(
    [
        video_feats,
        tef
    ],
    dim=1
)


# --------------------------------------------------
# 3. Batch 차원 추가
# --------------------------------------------------

video_feats = video_feats.unsqueeze(0)

video_mask = torch.ones(
    1,
    n_frames
)


# --------------------------------------------------
# 4. Query Feature 생성
# --------------------------------------------------

extractor = ClipFeatureExtractor(
    framerate=1 / 2,
    size=224,
    centercrop=True,
    model_name_or_path="ViT-B/32",
    device="cpu"
)

query_feats = extractor.encode_text(
    [query]
)


# --------------------------------------------------
# 5. Query padding + normalization
# --------------------------------------------------

query_feats, query_mask = pad_sequences_1d(
    query_feats,
    dtype=torch.float32,
    device="cpu",
    fixed_length=None
)

query_feats = F.normalize(
    query_feats,
    dim=-1,
    eps=1e-5
)


# --------------------------------------------------
# 6. Moment-DETR 입력 딕셔너리 구성
# --------------------------------------------------

model_inputs = {
    "src_vid": video_feats,
    "src_vid_mask": video_mask,
    "src_txt": query_feats,
    "src_txt_mask": query_mask
}


# --------------------------------------------------
# 7. Shape 확인
# --------------------------------------------------

print()
print("=== Moment-DETR Input Shapes ===")

for key, value in model_inputs.items():

    print(
        f"{key}: {value.shape}"
    )