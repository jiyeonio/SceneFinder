# multilingual-e5-large 추가 학습(fine-tuning) 계획

서비스의 자막 검색 모델(fine-tuned MiniLM)을 학습한 것과 같은 한국어 데이터로 `intfloat/multilingual-e5-large`를 추가 학습하는 계획입니다.
**아직 학습하지 않았고, 아래 시간·메모리는 추정치입니다.** 근거는 [embedding_compare.md](embedding_compare.md)입니다.
추가 학습하지 않은 e5-large는 설명문 검색에서 dev·test 모두 MiniLM보다 나았고, 자막 검색에서는 dev에서만 잡음 수준을 넘게 나았습니다.

## 기존 MiniLM 학습 자료 위치

| 항목 | 위치 | 상태 |
|---|---|---|
| 설명 문서 | `ai/experiments/korean_minilm/README.md` | 레포에 있음 |
| 데이터 전처리 | `ai/experiments/korean_minilm/prepare_data.py` | 레포에 있음 |
| 학습 | `ai/experiments/korean_minilm/train.py` | 레포에 있음 |
| 평가 (텍스트 검색 R@1·R@5·MRR) | `ai/experiments/korean_minilm/evaluate.py` | 레포에 있음 |
| 기존 평가 결과 | `ai/experiments/korean_minilm/results/full_validation_metrics.json` | 레포에 있음 |
| 원본 데이터: AI-Hub `TL_12`(학습)·`VL_12`(검증) TAR | 레포에 넣지 않음 (AI-Hub 이용 조건) | **이 서버에서 찾지 못함** |
| 전처리 결과 JSONL (`minilm_train_pairs_clean.jsonl` 15,502쌍, `minilm_val_pairs.jsonl` 1,948쌍) | 레포에 넣지 않음 | **이 서버에서 찾지 못함** |
| 학습된 MiniLM 모델 (`SCENEFINDER_MINILM_MODEL_PATH`) | README에 따르면 Google Drive에 보존 | 이 서버에서는 `/tmp` 아래에 있음 |

- 데이터는 AI-Hub 한국어 데이터의 요약문(질의)과 대화문(정답 텍스트) 쌍입니다. 영상 장면 검색용 데이터가 아니라 텍스트 검색용 쌍입니다.
- **학습된 MiniLM이 `/tmp` 아래에 있어 서버를 다시 시작하면 지워질 수 있습니다.** 서비스가 이 모델을 쓰므로 `/tmp` 밖으로 옮기고
  `.env` 경로를 바꾸는 것을 권장합니다(사용자 확인 필요).

## 학습 방식 (MiniLM과 같게, e5에 맞춰 일부 변경)

| 항목 | MiniLM (기존) | e5-large 계획 |
|---|---|---|
| 기본 모델 | paraphrase-multilingual-MiniLM-L12-v2 (약 1.2억 파라미터) | multilingual-e5-large (약 5.6억 파라미터, XLM-R large) |
| 손실 함수 | MultipleNegativesRankingLoss (같은 묶음의 다른 쌍을 오답으로) | 같음. 묶음을 키우려면 CachedMultipleNegativesRankingLoss |
| 입력 앞 문구 | 없음 | 질의 `query: `, 정답 텍스트 `passage: ` (e5 사용법) |
| 묶음 크기 | 8 (gradient accumulation 2) | 32 (메모리가 되면 64). MNRL은 묶음 안의 오답 수가 묶음 크기라 accumulation으로는 효과가 같지 않음 |
| 학습률 / warmup | 2e-5 / 10% | 1e-5 / 10% (큰 모델이 이미 잘하므로 너무 바꾸지 않게) |
| epoch | 1 | 1 (결과를 보고 2까지) |
| 최대 길이 / 정밀도 | 128토큰 / fp16 | 같음 |

- 토크나이저: 두 모델 모두 XLM-R 토크나이저를 써서, 기존 전처리의 128토큰 기준을 그대로 써도 됩니다.
- `train.py`는 기본 모델 이름이 코드에 고정돼 있어, 기본 모델·앞 문구·묶음 크기·손실 함수를 옵션으로 받도록 고쳐야 합니다.
  `evaluate.py`도 e5 앞 문구를 붙이도록 고쳐야 합니다.

## 필요 GPU 메모리·시간 (추정)

| 항목 | 추정 | 근거 |
|---|---|---|
| 모델·학습 상태 | 약 9GB | 5.6억 파라미터 × (fp32 가중치 4B + 기울기 4B + Adam 상태 8B) |
| 활성값 (묶음 32쌍 = 64문장, 128토큰, fp16) | 약 2~4GB | 24층·hidden 1024 기준 |
| **합계** | **약 12~14GB** (묶음 64면 약 15~18GB) | RTX A5000 24GB에 들어감. 백엔드(약 3GB, Whisper 분석 중 +2.5GB)와 같이 쓰면 묶음 32 권장 |
| 학습 시간 (15,502쌍, 1 epoch) | **약 5~15분** | A5000 fp16에서 XLM-R large 128토큰 학습 처리량 초당 약 50~120문장 가정 |
| 평가 | 텍스트 검색 1,948쌍 1분 이내, dev 장면 검색 비교 약 1분 | embedding_compare 실측(색인 34초) 기준 |

- 이 서버에서 재지 않은 추정입니다. 실제 학습 전에 가짜 문장으로 20스텝만 돌려 메모리·속도를 확인하는 것을 권장합니다(1분 안팎).

## 진행 순서

1. AI-Hub `TL_12`·`VL_12`를 다시 받거나 Google Drive의 전처리 JSONL을 서버로 가져오기(이용 조건 확인). 레포에는 넣지 않음.
2. `prepare_data.py`로 JSONL 만들기(이미 있으면 생략). 기존 수치(15,502 / 1,948쌍)와 같은지 확인.
3. `train.py`·`evaluate.py`에 기본 모델·e5 앞 문구·묶음 크기·손실 함수 옵션 추가.
4. 짧은 시험 실행(가짜 문장 20스텝)으로 메모리·속도 확인.
5. 학습 → 텍스트 검색 평가(기존 MiniLM 75.15% R@1과 비교) → **dev**에서 장면 검색 비교(`embedding_compare.py`에 학습한 모델 추가).
6. dev에서 추가 학습 전 e5-large보다 나을 때만 다음 단계로.

## 주의할 점

- **test는 이미 한 번 썼습니다**(e5-large 확인). 학습한 모델을 같은 test로 다시 확인하면 test에 맞춰 고르는 위험이 커집니다.
  새 test 질의를 만들거나, 같은 test를 쓰면 그 사실을 문서에 적어야 합니다.
- 학습 데이터(요약문 ↔ 대화문)는 서비스 질의(짧은 검색어 ↔ 자막 1~3문장)와 모양이 다릅니다. MiniLM은 이 학습으로 텍스트 검색이
  51% → 75%(R@1)로 올랐지만, 추가 학습하지 않은 e5-large가 장면 검색에서는 이미 MiniLM과 같거나 나았습니다. 추가 학습이 장면 검색을
  더 올린다는 보장은 없고, 오히려 일반 성능이 떨어질 수 있어 5번 비교가 필요합니다.
- 서비스 자막 검색에 쓰면 검색마다 영상당 최대 약 1.3초, GPU 약 2GB가 더 듭니다([embedding_compare.md](embedding_compare.md)의 「서비스에서 더해지는 시간」).
  자막 창 임베딩을 분석 때 저장하도록 바꾸면 검색 지연은 없앨 수 있습니다.
