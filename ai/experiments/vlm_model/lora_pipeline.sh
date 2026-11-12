#!/usr/bin/env bash
# 화면 검색 LoRA와 구간 검색 추가 학습(탐색적)을 창 없이 이어서 돌림. test는 돌리지 않음. 커밋하지 않음.
#   학습 영상 다운로드 끝 대기 → 자막·프레임·특징(prep) → 질의 생성(gen) → 유출 검사(filter)
#   → LoRA mix / welfare 학습(epoch마다 dev 특징) → dev 평가 4개 → 고르기 → 구간 검색 추가 학습 → dev 평가
#   tmux new-session -d -s lora "bash ~/scenefinder/ai/experiments/vlm_model/lora_pipeline.sh; sleep 604800"
set -uo pipefail
REPO=/home/team22/scenefinder; V=$REPO/ai/experiments/vlm_model; PY=$REPO/.venv/bin/python
D=/nfs/team/data/scenefinder_vlm; RUNS=$D/lora_runs; MR=$D/mr_runs; ST=$RUNS/state; LOG=$RUNS/pipeline.log
export HF_HOME=/nfs/team/data/huggingface HF_HUB_CACHE=/nfs/team/data/huggingface/hub HF_HUB_OFFLINE=1
mkdir -p "$ST" "$RUNS/logs"; cd "$REPO"
say() { echo "$(date '+%F %T') $*" | tee -a "$LOG"; }
stage() {   # stage <이름> <명령...>  (완료 표시로 이어하기, 한 번 다시 시도, 두 번 실패하면 멈춤)
  local name=$1; shift; local done_f="$ST/$name.done" slog="$RUNS/logs/$name.log"
  [ -f "$done_f" ] && { say "단계 $name: 이미 끝남"; return 0; }
  for try in 1 2; do
    say "단계 $name 시작 (${try}회째)"; local t0=$(date +%s)
    if "$@" >> "$slog" 2>&1; then date '+%F %T' > "$done_f"; say "단계 $name 끝 ($(( ($(date +%s) - t0) / 60 ))분)"; return 0; fi
    say "단계 $name 실패 (${try}회째):"; tail -15 "$slog" | sed 's/^/    /' | tee -a "$LOG"
    [ $try -eq 1 ] && sleep 120
  done
  say "단계 $name 두 번 실패 → 멈춤"; exit 1
}

N=$(($(wc -l < $REPO/docs/experiments/vlm_lora_train_videos.tsv) - 1))
say "학습 영상 다운로드 끝 대기 ($N개)"
missing() { tail -n +2 $REPO/docs/experiments/vlm_lora_train_videos.tsv | cut -f1 | while read v; do [ -f "$D/lora_videos/$v.mp4" ] || echo "$v"; done | wc -l; }
until [ "$(missing)" -eq 0 ] || grep -q "중단" $D/lora_videos/download.log; do sleep 60; done
say "받은 영상 $((N - $(missing)))/$N"

stage 01_prep   $PY $V/lora_make_data.py prep
stage 02_gen    $PY $V/lora_make_data.py gen
stage 03_filter $PY $V/lora_make_data.py filter
stage 04_lora_mix     $PY $V/lora_train.py --variant mix --out $RUNS
stage 05_lora_welfare $PY $V/lora_train.py --variant welfare --out $RUNS
for v in mix welfare; do for e in 1 2; do
  stage 06_eval_${v}_ep$e $PY $V/prelim_eval.py --methods F-VLM --lora $RUNS/$v/ep$e/adapter.pt --out $RUNS/$v/ep$e/dev_eval
done; done
stage 07_select $PY $V/lora_select.py --runs $RUNS --out $RUNS/selected.json
stage 08_mr_ft  $PY $V/mr_finetune.py --root $MR
CK=$($PY -c "import json;print(json.load(open('$MR/state_ft/vlm_tok_ko_ft.json'))['ckpt'])")
for cfg in "0 0" "45 23"; do set -- $cfg
  stage 09_mr_ft_dev_w$1 $PY $V/mr_eval_dev.py --root $MR --out $MR/dev_eval_ft/w$1_s$2 --win $1 --stride $2 \
    --models vlm_tok_ko,vlm_tok_ko_ft --ckpt vlm_tok_ko_ft=$CK
done
say "모두 끝 (test는 돌리지 않음, 커밋 전)"
