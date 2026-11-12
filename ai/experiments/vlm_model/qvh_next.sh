#!/usr/bin/env bash
# qvh_pipeline.sh(다운로드 → 압축 풀기 → 영상 특징) 뒤에 이어서 창 없이 도는 단계:
#   1 번역(영→한, Qwen3-VL-4B) → 2 질의 특징 → 3 학습 데이터 → 4 CLIP 버전 재현 학습
#   → 5·6 VLM 버전(영어+한국어, 질의 토큰/1벡터) → 7 질의 특징 종류 선택 → 8·9 VLM 버전(영어만/한국어만)
#   → 10 다른 언어 val 평가 → 11 복지 dev 평가 → 12 결과 문서 초안
# 규칙: test 평가는 하지 않음. 단계마다 완료 표시(<root>/state/stage_*.done)로 이어하기. 실패하면 원인을 로그에 남기고 멈춤.
#       GPU 단계는 하나씩, 다른 프로세스가 GPU를 쓰고 있으면 끝날 때까지 기다림. 커밋하지 않음.
#   tmux new-session -d -s qvh_next "bash ~/scenefinder/ai/experiments/vlm_model/qvh_next.sh"
#   시험: SMOKE=1 ROOT=<폴더> VIDEOS=<영상 폴더> N_EPOCH=3 bash qvh_next.sh
set -uo pipefail

REPO=/home/team22/scenefinder
Q=/nfs/team/data/scenefinder_vlm/qvh
ROOT=${ROOT:-/nfs/team/data/scenefinder_vlm/mr_runs}
VIDEOS=${VIDEOS:-$Q/videos/videos}
FEATS=${FEATS:-$Q/features/qwen3vl_emb2b_640}
TEXT_KO=${TEXT_KO:-$Q/text_ko}
TEXT_FEATS=${TEXT_FEATS:-$Q/text_feats/qwen3vl_emb2b}
DRAFT=${DRAFT:-$REPO/docs/experiments/vlm_mr_results_draft.md}
LOG=${LOG:-$Q/pipeline.log}
SMOKE=${SMOKE:-0}; N_EPOCH=${N_EPOCH:-}
PY=$REPO/.venv/bin/python
V=$REPO/ai/experiments/vlm_model
export HF_HOME=/nfs/team/data/huggingface HF_HUB_CACHE=/nfs/team/data/huggingface/hub HF_HUB_OFFLINE=1
mkdir -p "$ROOT/state" "$ROOT/logs"
cd "$REPO"

say() { echo "$(date '+%F %T') [next] $*" | tee -a "$LOG"; }

wait_gpu() {   # 우리 것이 아닌 GPU 계산 프로세스가 있으면 기다림
  local n=0
  while nvidia-smi --query-compute-apps=pid --format=csv,noheader 2>/dev/null | grep -q .; do
    [ $n -eq 0 ] && say "다른 프로세스가 GPU 사용 중 → 기다림: $(nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv,noheader | tr '\n' ' ')"
    n=$((n + 1)); sleep 300
  done
}

stage() {   # stage <이름> <gpu|cpu> <명령...>
  local name=$1 dev=$2; shift 2
  local done_f="$ROOT/state/stage_${name}.done" slog="$ROOT/logs/stage_${name}.log"
  if [ -f "$done_f" ]; then say "단계 $name: 이미 끝남 → 건너뜀"; return 0; fi
  [ "$dev" = gpu ] && wait_gpu
  local try t0
  for try in 1 2; do   # 일시적인 오류(네트워크·GPU 메모리 등)를 넘기려고 한 번만 다시 시도 (각 단계는 이어하기 가능)
    say "단계 $name 시작 (${try}회째)"
    t0=$(date +%s)
    if "$@" >> "$slog" 2>&1; then
      date '+%F %T' > "$done_f"
      say "단계 $name 끝 ($(( ($(date +%s) - t0) / 60 ))분)"
      return 0
    fi
    say "단계 $name 실패 (${try}회째). 로그 $slog 마지막 15줄:"
    tail -15 "$slog" | sed 's/^/    /' | tee -a "$LOG"
    [ $try -eq 1 ] && { say "10분 뒤 한 번 더 시도"; sleep 600; [ "$dev" = gpu ] && wait_gpu; }
  done
  say "단계 $name 두 번 실패 → 멈춤"
  exit 1
}

# 0) 영상 특징 단계(qvh_pipeline.sh)가 끝나기를 기다리고 결과 확인
if [ "$SMOKE" != 1 ]; then
  say "영상 특징 단계(qvh_pipe)가 끝나기를 기다림"
  until grep -q "파이프라인 끝" "$Q/pipeline.log"; do
    if ! tmux has-session -t qvh_pipe 2>/dev/null; then say "qvh_pipe 세션이 끝났는데 '파이프라인 끝'이 없음 → 멈춤"; exit 1; fi
    sleep 300
  done
  NV=$(find "$VIDEOS" -name '*.mp4' | wc -l); NF=$(ls "$FEATS"/*.npz 2>/dev/null | wc -l)
  say "영상 ${NV}개, 특징 ${NF}개"
  if [ "$NF" -lt $((NV * 95 / 100)) ] || [ "$NF" -lt 9000 ]; then
    say "특징 파일이 너무 적음(영상의 95% 또는 9000개 미만) → 멈춤. 확인: $FEATS/progress.log"; exit 1
  fi
fi

LIMIT=()
if [ "$SMOKE" = 1 ]; then ls "$FEATS"/*.npz | xargs -n1 basename | sed 's/\.npz$//' > "$ROOT/smoke_vids.txt"; LIMIT=(--limit_vids "$ROOT/smoke_vids.txt"); fi
EP=(); [ -n "$N_EPOCH" ] && EP=(--n_epoch "$N_EPOCH")
QD=/home/team22/jiyeon_experiment/pinpoint-capstone/ai/external/moment_detr/data
ARGS=(--root "$ROOT" --vlm_feats "$FEATS" --text_feats "$TEXT_FEATS" --text_ko "$TEXT_KO" "${EP[@]}")

stage 01_translate gpu $PY $V/qvh_translate.py --out "$TEXT_KO" "${LIMIT[@]}"
stage 02_text_feats gpu $PY $V/qvh_text_features.py --out "$TEXT_FEATS" \
  --jsonl "$QD/highlight_train_release.jsonl" "$QD/highlight_val_release.jsonl" "$TEXT_KO/train_ko.jsonl" "$TEXT_KO/val_ko.jsonl"
stage 03_prepare cpu $PY $V/mr_runs.py prepare "${ARGS[@]}"
stage 04_train_clip_repro gpu $PY $V/mr_runs.py train clip_repro "${ARGS[@]}"
stage 05_train_vlm_tok_enko gpu $PY $V/mr_runs.py train vlm_tok_enko "${ARGS[@]}"
stage 06_train_vlm_pooled_enko gpu $PY $V/mr_runs.py train vlm_pooled_enko "${ARGS[@]}"
stage 07_select cpu $PY $V/mr_runs.py select "${ARGS[@]}"
SEL=$($PY -c "import json;print(json.load(open('$ROOT/state/selected_text_feat.json'))['selected'])")
say "질의 특징 종류: $SEL"
stage 08_train_vlm_${SEL}_en gpu $PY $V/mr_runs.py train vlm_${SEL}_en "${ARGS[@]}"
stage 09_train_vlm_${SEL}_ko gpu $PY $V/mr_runs.py train vlm_${SEL}_ko "${ARGS[@]}"
for n in vlm_tok_enko vlm_pooled_enko vlm_${SEL}_en vlm_${SEL}_ko; do
  stage 10_eval_other_$n gpu $PY $V/mr_runs.py eval_other $n "${ARGS[@]}"
done
stage 11_dev_eval gpu $PY $V/mr_eval_dev.py --root "$ROOT" --out "$ROOT/dev_eval"
stage 12_report cpu $PY $V/mr_report.py --root "$ROOT" --dev "$ROOT/dev_eval" --out "$DRAFT" --text_ko "$TEXT_KO"
say "모두 끝. 결과 문서 초안: $DRAFT (커밋 전, test는 돌리지 않음)"
