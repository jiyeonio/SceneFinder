#!/usr/bin/env bash
# QVH 다운로드가 끝나면 이어서: (빠진 조각 다시 받기) → 압축 풀기 → 영상 수 확인 → Qwen3-VL-Embedding 특징 추출.
# 창 없이 돌도록 tmux 세션에서 실행한다:
#   tmux new-session -d -s qvh_pipe "bash ~/scenefinder/ai/experiments/vlm_model/qvh_pipeline.sh"
# 진행 로그: /nfs/team/data/scenefinder_vlm/qvh/pipeline.log
set -uo pipefail

REPO=/home/team22/scenefinder
Q=/nfs/team/data/scenefinder_vlm/qvh
PARTS=$Q/parts
LOG=$Q/pipeline.log
PY=$REPO/.venv/bin/python
export HF_HOME=/nfs/team/data/huggingface HF_HUB_CACHE=/nfs/team/data/huggingface/hub HF_HUB_OFFLINE=1

say() { echo "$(date '+%F %T') $*" | tee -a "$LOG"; }
nparts() { ls "$PARTS"/*.part 2>/dev/null | wc -l; }
downloading() { pgrep -f '^bash ai/experiments/vlm_model/qvh_download.sh' >/dev/null; }

cd "$REPO"
N=$(cat "$PARTS/N_PARTS")
say "파이프라인 시작: 다운로드 끝나기를 기다림 (지금 $(nparts)/$N 조각)"
while downloading; do sleep 60; done
say "다운로드 스크립트 끝남: $(nparts)/$N 조각"

# 1) 빠진 조각이 있으면 두 번까지 다시 받기 (이어받기)
for try in 1 2; do
  [ "$(nparts)" -ge "$N" ] && break
  say "빠진 조각 $((N - $(nparts)))개 → 다시 받기 ($try회)"
  bash ai/experiments/vlm_model/qvh_download.sh "$PARTS" 32 >> "$Q/download.log" 2>&1
done
say "다운로드 최종: $(nparts)/$N 조각 (모자라면 앞에서부터 이어지는 데까지만 풂)"

# 2) 압축 풀기 (앞에서부터 이어지는 조각까지)
say "압축 풀기 시작 → $Q/videos"
bash ai/experiments/vlm_model/qvh_extract.sh "$PARTS" "$Q/videos" >> "$LOG" 2>&1
NV=$(find "$Q/videos" -name '*.mp4' | wc -l)
say "압축 풀기 끝: 영상 ${NV}개 (annotations 영상 10,148개)"
$PY - "$Q/videos" >> "$LOG" 2>&1 <<'EOF'
import json, sys
from pathlib import Path
A = Path("/home/team22/jiyeon_experiment/pinpoint-capstone/ai/external/moment_detr/data")
have = {p.stem for p in Path(sys.argv[1]).rglob("*.mp4")}
for sp in ("train", "val", "test"):
    vids = {json.loads(l)["vid"] for l in open(A / f"highlight_{sp}_release.jsonl")}
    print(f"  {sp}: annotations {len(vids)}개 중 영상 있음 {len(vids & have)}개")
EOF

# 3) 특징 추출 (이미 있는 파일은 건너뜀)
say "특징 추출 시작 (Qwen3-VL-Embedding-2B, 640x360, 2초마다 1장)"
$PY ai/experiments/vlm_model/qvh_features.py --videos "$Q/videos/videos" --out "$Q/features/qwen3vl_emb2b_640" >> "$LOG" 2>&1
say "파이프라인 끝 (특징 $(ls $Q/features/qwen3vl_emb2b_640/*.npz 2>/dev/null | wc -l)개)"
