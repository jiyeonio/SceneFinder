# 인수인계 메모 (2026-11-12 17:00 KST 기준)

시간은 모두 한국 시간(KST). 서버 시계는 UTC라 로그 시각은 9시간 빠릅니다.

## 브랜치

| 브랜치 | 내용 | 상태 |
|---|---|---|
| `vlm/model` | 모델 실험(구간 검색 VLM 버전, 화면 검색 LoRA, N3 결합, VLM 재판별), 평가 계획·결과 문서 | 커밋 끝, push 안 함 |
| `welfare/service` | 복지바로봄 시연 서비스(백엔드 API + 팀원 프론트 `frontend-ui` 67f564f 기반). `vlm/model`을 머지해 둠 | 커밋 끝, push 안 함 |
| `main` | 기존 서비스. 손대지 않음 | — |

## 지금 결론 (실험)

- **최종 후보 = N3** (자막 MiniLM 상위 5 + LoRA 화면 검색 상위 3, 화면 구간 4초 앞당김, N1 후보 없음). dev R@1 IoU≥0.3 41/80 (B3 32).
  - N1 후보는 특징 추출 시간 한도(1.5초/영상 1분) 때문에 뺌(사용자 결정, 결과 본 뒤 변경으로 기록).
- **N3+VLM 재판별**(K5·A·mix): dev 43/80(+2) → 기준(3개 넘게) 미달. **정확도 향상이 아니라 「화면/자막 확인 표시」 기능으로 소개** ([proposal_memo.md](experiments/proposal_memo.md)).
- 구간 검색 VLM 버전: QVH 한국어 val R1@0.5 52.52 vs CLIP 영어 52.58, 복지 영상은 무작위 수준 → 비교 결과로만.
- 정답 없음 필터는 적용 안 함(한계) → 상위 3개 장면 + 공식 정책 패널로 보완.
- 문서: [vlm_model_plan.md](experiments/vlm_model_plan.md)(계획·판정 기준·일정), [vlm_lora_results_draft.md](experiments/vlm_lora_results_draft.md), [vlm_mr_results_draft.md](experiments/vlm_mr_results_draft.md), [vlm_start_metrics_dev.md](experiments/vlm_start_metrics_dev.md).

## 남은 일

### 사용자(검수·결정)

- [ ] **test 8개 검수** (11/13~14). 검수 서버:
  ```bash
  cd ~/scenefinder
  python tools/labeler/server.py --labels ai/experiments/vlm_model/labels/review.json \
      --youtube-list ai/experiments/vlm_model/labels/review_videos.tsv \
      --videos /nfs/team/data/scenefinder_vlm/eval_videos --port 8771
  ```
  브라우저 `http://127.0.0.1:8771` (VS Code PORTS에 8771 추가). 진행 확인: `python ai/experiments/vlm_model/review_set.py status`
- [ ] **기초연금 단계 카드 검수** (브라우저로 보고 따로 전달 예정). 검수 문서 [service/steps_review_basic-pension.md](service/steps_review_basic-pension.md), 파일 `backend/data/steps/<영상ID>.json`
  - `KBBwdz4sidM`(이렇게 하면된다!): 검수 반영 끝 — ②단계(1:49~2:18)만, `reviewed`
  - `NYNnaDN9d8M`(온라인 신청 홈페이지 편): ③(1:17)·④(9:31)는 맞음, **①·②가 인트로(0:00)로 잘못 잡힘** → 자막 참고: 신청 시기 0:23, 금융정보 제공 동의서 6:07~6:56, 서류 첨부 8:43~9:22
  - `GmxO1AZabqM`(모의계산), `yUhcwuj-yyk`(노래, 자막 없음): 초안 그대로 — 노래 영상은 단계 전부 빼는 것을 권함
- [ ] **11/15(일) 설정 고정 커밋 → test 1회**(사용자 지시 후). N3와 N3+VLM 재판별 두 설정 모두. test는 절대 자동으로 돌리지 않음.
- [ ] **11/15(일) 시연 영상 촬영.**

### 다음 작업(이어서 할 것)

- [ ] **청년 주거 영상 4개 재시도**: 11/13 10:00에 tmux `demo_dl_retry`가 자동 시작(40초 간격, 403이면 중단, 받은 6개는 건너뜀). 로그 `/nfs/team/data/scenefinder_vlm/demo/videos/download.log`
  - 받으면 미리 분석해야 시연 목록에 들어감(자동으로 안 함, GPU를 쓰므로 API 서버를 잠깐 내리고):
    ```bash
    cd ~/scenefinder && tmux kill-session -t welfare_api
    set -a && . backend/.env && set +a
    HF_HUB_OFFLINE=1 HF_HOME=/nfs/team/data/huggingface .venv/bin/python backend/scripts/index_demo.py
    # 그다음 아래 「서버 다시 띄우기」로 API 재시작, demo_queries.py로 4a 질문 다시 시험
    ```
  - 403이면 더 시도하지 말 것(서버 IP 차단 이력). 청년월세는 지금 dev 영상 1개뿐.
- [ ] 아이돌봄 단계 카드 초안(`python backend/scripts/draft_steps.py --policy child-care`, API 서버를 내린 뒤) — 우선순위 낮음.
- [ ] 청년월세 정책 연결: 새 영상이 들어오면 `POLICY_OF_HINT`(backend/services/welfare_service.py)에 맞는지 확인.

### 만들었지만 브라우저로 확인이 필요한 것

서버에서 화면 캡처가 안 돼(헤드리스 브라우저 시스템 라이브러리 없음) 코드·타입체크·빌드·API 응답으로만 확인했습니다.

- [x] 3번 질문 정책 맥락 입력창 — 시청 화면 「○○에 대해 물어보기」. 「이거 아직 신청 되는 거예요?」 → 「영상에는 해당 내용이 없어요」 + 공식 신청 기간. (검색 화면에서는 `#/results?q=이거%20아직%20신청%20되는%20거예요%3F&policy=basic-pension`)
- [x] 신청 단계 카드 클릭 → 그 장면으로 이동 + 큰 자막(구간 반복은 버튼 누를 때만)
- [x] 유튜브 자체 자막 끄기(cc_load_policy 0 + captions 모듈 내림), 일시정지 시 추천 화면 덮개, 「재생 중」 배지 삭제
- [x] 누른 장면이 항상 「찾은 장면」(VLM 확인 전후로 1위가 바뀌던 문제 수정), 진행바 이름 겹침 정리, 큰 자막은 영상 아래 칸
- [x] 검색 결과 배치: 맨 위 「바로 답」(1위 장면 + 공식 답변 + 문의 + 체크리스트), 다른 장면 작은 카드, 정책 카드 전체 너비, 확인 안 됨 장면은 맨 아래 접기
- [x] 문의는 정책 API 문의처만(하드코딩한 「24시간 · 129」 삭제), 모의계산·신청 전 꼭 확인·자주 묻는 질문(하드코딩) 삭제

### 알려진 한계

- verification 임계값(0.5)과 「영상에 답 없음」(VLM) 규칙은 dev에서 맞추지 않은 값.
- 「기초연금 신청할 때 뭐 챙겨가야 돼요?」(오프닝): 서류 장면(1:56)은 맞게 찾지만 배지는 「자막에서 확인됨」. 대안 질문 3개도 같음 → 원래 질문 그대로 쓰기로 함.
- VLM 확인은 영상 3개 기준 약 5초(기본 결과는 0.1초 안). 시연에서 배지가 바뀌는 데 몇 초 걸림.

## 서버 (창을 닫아도 tmux에서 계속 돎)

| tmux 세션 | 내용 |
|---|---|
| `welfare_api` | 백엔드 `backend/welfare_app.py` (포트 8000, SEARCH_MODEL=n3_vlm, GPU 약 13 GiB) |
| `welfare_web` | 프론트 vite (포트 5173, `/api`는 8000으로 넘김) |
| `demo_dl_retry` | 11/13 10:00 청년 주거 영상 재시도 |

접속: VS Code PORTS에 **5173** 추가 → `http://127.0.0.1:5173` (또는 `ssh -L 5173:127.0.0.1:5173 <계정>@<서버>`).

서버 다시 띄우기:
```bash
# 백엔드 (모델 올리는 데 약 1분)
tmux new-session -d -s welfare_api "cd ~/scenefinder && set -a && . backend/.env && set +a && HF_HUB_OFFLINE=1 HF_HOME=/nfs/team/data/huggingface SEARCH_MODEL=n3_vlm .venv/bin/uvicorn backend.welfare_app:app --host 127.0.0.1 --port 8000"
# 프론트
tmux new-session -d -s welfare_web "cd ~/scenefinder/frontend && PATH=$HOME/.local/node/node-v22.12.0-linux-x64/bin:\$PATH npx vite --host 127.0.0.1 --port 5173"
```
`frontend/.env.local`(커밋 안 함)에 `VITE_API_BASE_URL=http://127.0.0.1:5173`.

## 데이터 위치 (저장소 밖, NFS)

- `/nfs/team/data/scenefinder_vlm/demo/` — 시연 영상·색인(자막, LoRA 화면 특징, 프레임, CLIP)
- `/nfs/team/data/scenefinder_vlm/lora_runs/welfare/ep1/adapter.pt` — 고른 화면 검색 LoRA
- `/nfs/team/data/scenefinder_vlm/mr_runs/` — 구간 검색 학습 결과, `/nfs/team/data/scenefinder_vlm/qvh/` — QVH 영상·특징
- 저장소 안 시연 데이터: `backend/data/policies.json`(공공데이터, `python backend/scripts/build_policies.py`로 다시 받기), `backend/data/demo_videos.json`, `backend/data/steps/`
