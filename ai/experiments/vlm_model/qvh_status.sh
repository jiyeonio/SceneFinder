#!/usr/bin/env bash
# QVH 원본 다운로드 상태: 완료 조각 수, 받은 양, 10초 동안 잰 속도, 예상 남은 시간, tmux 세션·연결 수.
#
#   bash ai/experiments/vlm_model/qvh_status.sh
P=${1:-/nfs/team/data/scenefinder_vlm/qvh/parts}
TOTAL=$(cat "$P/TOTAL_BYTES"); N=$(cat "$P/N_PARTS")
a=$(du -sb "$P" | cut -f1); sleep 10; b=$(du -sb "$P" | cut -f1)
python3 - "$a" "$b" "$TOTAL" <<'EOF'
import sys
a, b, total = map(int, sys.argv[1:])
rate = (b - a) / 10
print(f"받은 양: {b / 1e9:.1f} / {total / 1e9:.1f} GB ({b / total * 100:.0f}%)")
print(f"속도(10초): {rate / 1e6:.1f} MB/s" + (f", 남은 시간 약 {(total - b) / rate / 3600:.1f}시간" if rate > 0 else ""))
EOF
echo "완료 조각: $(ls "$P"/*.part 2>/dev/null | wc -l) / $N"
echo "tmux 세션 qvh: $(tmux has-session -t qvh 2>/dev/null && echo 있음 || echo 없음), 연결 수: $(pgrep -fc '^curl -sS --retry 5' || echo 0)"
echo "로그 마지막 줄: $(tail -1 /nfs/team/data/scenefinder_vlm/qvh/download.log)"
echo "이어서 돌 작업(tmux qvh_pipe): $(tmux has-session -t qvh_pipe 2>/dev/null && echo 있음 || echo 없음)"
echo "파이프라인 로그 마지막 줄: $(tail -1 /nfs/team/data/scenefinder_vlm/qvh/pipeline.log 2>/dev/null)"
F=/nfs/team/data/scenefinder_vlm/qvh/features/qwen3vl_emb2b_640
[ -d "$F" ] && echo "특징 파일: $(ls "$F"/*.npz 2>/dev/null | wc -l) / 약 10148  ($(tail -1 "$F/progress.log" 2>/dev/null))"
echo "다음 단계(tmux qvh_next): $(tmux has-session -t qvh_next 2>/dev/null && echo 있음 || echo 없음), 마지막: $(grep '\[next\]' /nfs/team/data/scenefinder_vlm/qvh/pipeline.log | tail -1)"
ls /nfs/team/data/scenefinder_vlm/mr_runs/state/stage_*.done 2>/dev/null | xargs -n1 basename 2>/dev/null | sed 's/^stage_//;s/\.done$//' | tr '\n' ' ' | sed 's/^/끝난 단계: /'; echo
