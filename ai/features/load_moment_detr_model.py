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
# Moment-DETR model utility import
# --------------------------------------------------

from run_on_video.model_utils import (
    build_inference_model
)


# --------------------------------------------------
# Checkpoint 경로
# --------------------------------------------------

checkpoint_path = (
    MOMENT_DETR_ROOT
    / "run_on_video"
    / "moment_detr_ckpt"
    / "model_best.ckpt"
)


# --------------------------------------------------
# Checkpoint 파일 확인
# --------------------------------------------------

if not checkpoint_path.exists():

    raise FileNotFoundError(
        f"Checkpoint를 찾을 수 없습니다: "
        f"{checkpoint_path}"
    )


print("Checkpoint 파일 확인 완료!")
print(checkpoint_path)


# --------------------------------------------------
# Model Load
# --------------------------------------------------

print()
print("Moment-DETR 모델 로드 시작...")


model = build_inference_model(
    str(checkpoint_path)
)

model = model.to("cpu")


print()
print("Moment-DETR 모델 로드 성공!")

print(
    "Model type:",
    type(model)
)