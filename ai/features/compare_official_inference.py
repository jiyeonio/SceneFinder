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
# 공식 Predictor import
# --------------------------------------------------

from run_on_video.run import (
    MomentDETRPredictor
)


# --------------------------------------------------
# 설정
# --------------------------------------------------

video_path = "data/raw/test_audio.mp4"

query = (
    "the steak is flipped "
    "while cooking in the pan"
)

checkpoint_path = (
    MOMENT_DETR_ROOT
    / "run_on_video"
    / "moment_detr_ckpt"
    / "model_best.ckpt"
)


# --------------------------------------------------
# 공식 Predictor 생성
# --------------------------------------------------

print("공식 MomentDETRPredictor 생성...")

predictor = MomentDETRPredictor(
    ckpt_path=str(checkpoint_path),
    clip_model_name_or_path="ViT-B/32",
    device="cpu"
)

predictor.model.eval()


# --------------------------------------------------
# 공식 inference
# --------------------------------------------------

print()
print("공식 inference 시작...")

predictions = predictor.localize_moment(
    video_path=video_path,
    query_list=[query]
)


# --------------------------------------------------
# 결과 출력
# --------------------------------------------------

print()
print("====================================")
print(" Official Moment-DETR Result")
print("====================================")

print(
    "Query:",
    predictions[0]["query"]
)

print()
print(
    "Predicted windows:"
)

for result in predictions[0][
    "pred_relevant_windows"
][:5]:

    print(result)