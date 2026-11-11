#!/usr/bin/env bash
# QVHighlights 원본 영상(qvhilights_videos.tar.gz, 143.7GB)을 128MiB 조각으로 나눠 앞에서부터 순서대로 받는다.
# 연결당 약 33KB/s라 32개를 동시에 받는다(합계 약 1MB/s, 전체 약 38시간).
# 다시 실행하면 다 받은 조각은 건너뛰고, 받다 만 조각은 이어 받는다.
# 앞쪽 조각부터 완성되므로 qvh_extract.sh로 받은 만큼만 먼저 풀 수 있다.
#
#   bash ai/experiments/vlm_model/qvh_download.sh [저장 폴더] [동시 연결 수]
set -euo pipefail

URL=https://nlp.cs.unc.edu/data/jielei/qvh/qvhilights_videos.tar.gz
OUT=${1:-/nfs/team/data/scenefinder_vlm/qvh/parts}
JOBS=${2:-32}
CHUNK=$((128 * 1024 * 1024))

mkdir -p "$OUT"
TOTAL=$(curl -sI "$URL" | tr -d '\r' | awk 'tolower($1)=="content-length:"{print $2}')
[ -n "$TOTAL" ] || { echo "파일 크기를 못 읽음" >&2; exit 1; }
N=$(( (TOTAL + CHUNK - 1) / CHUNK ))
echo "$TOTAL" > "$OUT/TOTAL_BYTES"
echo "$N" > "$OUT/N_PARTS"
echo "$(date '+%F %T') 시작: ${TOTAL} bytes, 조각 ${N}개, 동시 ${JOBS}개"

fetch() {
  local i=$1 start end want f
  start=$((i * CHUNK)); end=$((start + CHUNK - 1))
  [ "$end" -ge "$TOTAL" ] && end=$((TOTAL - 1))
  want=$((end - start + 1))
  f=$(printf '%s/%05d.part' "$OUT" "$i")
  [ -f "$f" ] && [ "$(stat -c %s "$f")" -eq "$want" ] && return 0
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    local have=0
    [ -f "$f.tmp" ] && have=$(stat -c %s "$f.tmp")
    if [ "$have" -lt "$want" ]; then
      curl -sS --retry 5 --retry-all-errors --connect-timeout 30 --speed-limit 1024 --speed-time 120 \
        -r "$((start + have))-$end" "$URL" >> "$f.tmp" || true
      have=$(stat -c %s "$f.tmp" 2>/dev/null || echo 0)
    fi
    if [ "$have" -eq "$want" ]; then mv "$f.tmp" "$f"; return 0; fi
    if [ "$have" -gt "$want" ]; then rm -f "$f.tmp"; fi
    sleep 10
  done
  echo "$(date '+%F %T') 실패: 조각 $i" >&2
  return 1
}
export -f fetch
export URL OUT CHUNK TOTAL

seq 0 $((N - 1)) | xargs -P "$JOBS" -I{} bash -c 'fetch {}'
echo "$(date '+%F %T') 끝: $(ls "$OUT"/*.part | wc -l)/$N 조각"
