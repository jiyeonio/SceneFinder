#!/usr/bin/env bash
# qvh_download.sh가 받은 조각을 0번부터 이어지는 데까지 이어 붙여 tar로 푼다.
# 비어 있는 조각을 만나면 기다렸다가 이어서 푼다(--wait). 다운로드가 덜 끝났을 때
# 받은 만큼만 풀고 멈추려면 --wait 없이 실행한다(마지막 영상은 잘려 있을 수 있어 tar 오류가 나도 무시).
#
#   bash ai/experiments/vlm_model/qvh_extract.sh [조각 폴더] [풀 폴더] [--wait]
set -uo pipefail

PARTS=${1:-/nfs/team/data/scenefinder_vlm/qvh/parts}
DEST=${2:-/nfs/team/data/scenefinder_vlm/qvh/videos}
WAIT=${3:-}
N=$(cat "$PARTS/N_PARTS")
mkdir -p "$DEST"

stream() {
  local i f
  for ((i = 0; i < N; i++)); do
    f=$(printf '%s/%05d.part' "$PARTS" "$i")
    while [ ! -f "$f" ]; do
      [ "$WAIT" = "--wait" ] || { echo "조각 $i 없음, 여기까지 품" >&2; return 0; }
      sleep 60
    done
    cat "$f"
  done
}

stream | tar -xz -C "$DEST" --skip-old-files
echo "$(date '+%F %T') 영상 $(find "$DEST" -name '*.mp4' | wc -l)개"
