from pathlib import Path
import sys


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
# Import
# --------------------------------------------------

from run_on_video.data_utils import (
    ClipFeatureExtractor
)


# --------------------------------------------------
# Query
# --------------------------------------------------

query = (
    "the steak is flipped "
    "while cooking in the pan"
)


# --------------------------------------------------
# CLIP extractor 생성
# --------------------------------------------------

extractor = ClipFeatureExtractor(
    framerate=1 / 2,
    size=224,
    centercrop=True,
    model_name_or_path="ViT-B/32",
    device="cpu"
)


# --------------------------------------------------
# Query Feature 추출
# --------------------------------------------------

print("Query Feature 추출 시작...")

query_features = extractor.encode_text(
    [query]
)

print("Query Feature 추출 성공!")

print(
    "반환 타입:",
    type(query_features)
)

print(
    "리스트 길이:",
    len(query_features)
)

print(
    "첫 번째 Query Feature shape:",
    query_features[0].shape
)