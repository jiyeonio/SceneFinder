# SceneFinder Korean MiniLM Fine-tuning

## 1. 개요

SceneFinder는 사용자가 자연어로 원하는 장면을 검색하면,
영상 내부의 관련 시간 구간을 찾아주는 서비스입니다.

한국어 영상에서도 검색 성능을 개선하기 위해
기존 Moment-DETR 기반 영상 검색에
한국어 자막 의미 검색을 결합하는 Fusion 방식을 실험했습니다.

자막 의미 검색에는 다음 모델을 사용합니다.

- 기본 모델: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`
- 추가 학습 모델: 위 모델을 한국어 데이터로 Fine-tuning한 MiniLM

이 디렉터리는 MiniLM의 데이터 준비, 학습, 평가 방법과
실험 결과를 정리합니다.

**주의:** MiniLM은 영상 장면을 직접 분석하는 모델이 아닙니다.
텍스트 간 의미적 유사도를 계산하며,
영상 장면 검색은 별도의 Moment-DETR 계열 모델과 결합합니다.

---

## 2. 폴더 구성

~~~text
ai/
├── features/
│   ├── fusion_search.py
│   └── consensus_rerank.py
├── preprocessing/
│   └── transcribe_service.py
└── experiments/
    └── korean_minilm/
        ├── prepare_data.py
        ├── train.py
        ├── evaluate.py
        ├── README.md
        └── results/
            └── full_validation_metrics.json
~~~

각 파일의 역할:

| 파일 | 역할 |
|---|---|
| `prepare_data.py` | AI-Hub 학습·검증 데이터에서 텍스트 쌍 생성 |
| `train.py` | 기본 MiniLM Fine-tuning |
| `evaluate.py` | 기본 모델과 Fine-tuned 모델의 텍스트 검색 성능 비교 |
| `results/full_validation_metrics.json` | 전체 Validation 평가 결과 |
| `ai/features/fusion_search.py` | Moment-DETR 결과와 자막 의미 검색 결과 결합 |
| `ai/features/consensus_rerank.py` | 후보 구간 간 중첩을 활용한 순위 조정 |
| `ai/preprocessing/transcribe_service.py` | Whisper 음성 전사를 통한 자막 JSON 생성 |

---

## 3. 사용 데이터 및 전처리

AI-Hub 한국어 데이터의 `TL_12` 학습 TAR,
`VL_12` 검증 TAR를 사용한 실험입니다.

TAR 내부 ZIP의 JSON 라벨에서 다음 정보를 추출합니다.

- `query`: JSON의 `summary`
- `positive`: `video.term`의 `transcription`을 순서대로 결합한 텍스트
- `video_id`: `metadata.filename`

한 쌍은 다음과 같은 형식입니다.

~~~json
{
  "video_id": "example_video_id",
  "query": "검색 질문에 해당하는 요약문",
  "positive": "관련 대화 내용"
}
~~~

위 JSON은 설명을 위해 만든 가상 예시이며,
실제 AI-Hub 데이터 문장을 포함하지 않습니다.

전처리 조건:

1. 요약문과 대화문이 모두 존재하는 샘플만 사용
2. 기본 MiniLM 토크나이저 기준 각 텍스트 최대 128토큰
3. Validation의 `MYL_18127`, `MYL_18128` 제외
4. 학습·검증 영상 ID 중복 검사
5. 학습 데이터에서 중복된 query를 가진 샘플 제거
6. 원본 학습 쌍, 정제 학습 쌍, 검증 쌍을 JSONL로 저장

기존 실험의 데이터 규모:

| 데이터 | 쌍 개수 |
|---|---:|
| 원본 학습 쌍 | 15,823 |
| 중복 query 제거 후 학습 쌍 | 15,502 |
| 검증 쌍 | 1,948 |

학습과 검증의 영상 ID 중복은 0개였습니다.

이 숫자는 기존 실험에서 확인한 결과이며,
복구한 코드로 새 런타임에서 전처리를 재실행한 결과는 아닙니다.

---

## 4. 데이터 전처리 실행

프로젝트 루트에서 실행합니다.

~~~bash
python -m ai.experiments.korean_minilm.prepare_data \
  --train-tar "/path/to/TL_12_training.tar" \
  --val-tar "/path/to/VL_12_validation.tar" \
  --output-dir "/path/to/new_prepared_data"
~~~

생성되는 파일:

~~~text
new_prepared_data/
├── minilm_train_pairs.jsonl
├── minilm_train_pairs_clean.jsonl
└── minilm_val_pairs.jsonl
~~~

입력 TAR 파일명은 각각 `TL_12`, `VL_12`로 시작해야 합니다.

기존 파일을 실수로 덮어쓰지 않도록
출력 파일이 이미 존재하면 실행을 중단합니다.

---

## 5. MiniLM Fine-tuning

### 기본 모델

`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`

### 학습 방식

요약문을 Anchor, 대응하는 대화문을 Positive로 사용하여
`MultipleNegativesRankingLoss`로 학습합니다.

학습에서는 같은 배치 내의 다른 텍스트 쌍을
Negative 후보로 활용합니다.

### 학습 설정

| 항목 | 설정 |
|---|---|
| Epoch | 1 |
| Batch size | 8 |
| Gradient accumulation | 2 |
| Learning rate | 2e-5 |
| Warmup ratio | 0.1 |
| 최대 입력 길이 | 128 tokens |
| Loss | MultipleNegativesRankingLoss |
| Batch sampler | NO_DUPLICATES |
| FP16 | 사용 |
| Seed | 42 |
| 장치 | CUDA GPU |

### 학습 실행

~~~bash
python -m ai.experiments.korean_minilm.train \
  --train-jsonl "/path/to/minilm_train_pairs_clean.jsonl" \
  --output-dir "/path/to/new_training_output"
~~~

최종 모델 저장 위치:

~~~text
new_training_output/
└── final_model/
~~~

**이미 학습된 모델이 Google Drive에 보존되어 있으므로,
기존 결과를 사용하려는 경우 재학습할 필요가 없습니다.**

`train.py`는 기존 출력 디렉터리가 있으면
새 학습 실행을 거부하도록 작성되어 있습니다.

---

## 6. Validation 전체 평가

검증에는 총 1,948개의 한국어 텍스트 쌍을 사용했습니다.

각 query에 대해 검증 데이터의 모든 positive 텍스트와
코사인 유사도를 계산하고,
같은 인덱스의 positive를 정답으로 간주합니다.

평가 지표:

- **Recall@1:** 정답 텍스트가 1위인 비율
- **Recall@5:** 정답 텍스트가 상위 5위 이내에 있는 비율
- **MRR:** 정답 순위의 역수 평균

### 평가 실행

~~~bash
python -m ai.experiments.korean_minilm.evaluate \
  --val-jsonl "/path/to/minilm_val_pairs.jsonl" \
  --finetuned-model "/path/to/final_model" \
  --output "/path/to/new_evaluation.json"
~~~

### 기존 평가 결과

| 지표 | 기본 MiniLM | Fine-tuned MiniLM |
|---|---:|---:|
| Recall@1 | 51.03% | 75.15% |
| Recall@5 | 65.55% | 85.88% |
| MRR | 0.5773 | 0.7996 |

원래 평가 결과는 기존 실험에서 재현 검증했으며,
정확한 수치는 `results/full_validation_metrics.json`에 기록했습니다.

**이 결과는 한국어 요약문과 대화문 사이의 텍스트 검색 성능입니다.**

영상에서 정답 시간 구간을 찾는 성능인
R1@0.5, mAP, 시간 구간 IoU와 동일한 지표가 아닙니다.

또한 요약문과 대화문이 동일한 원천 데이터에서 생성된
텍스트 쌍을 대상으로 한 평가이므로,
실제 서비스의 사용자 질의 성능을 그대로 보장하지 않습니다.

---

## 7. Fusion 검색 모델 연결

`ai/features/fusion_search.py`의
`predict_moments_fusion()`에 `model_type`을 전달합니다.

- `model_type="base"`: 공개 기본 MiniLM 사용
- `model_type="finetuned"`: 학습 완료된 MiniLM 사용

Fine-tuned 모델은 다음 환경변수로 경로를 지정합니다.

~~~python
import os

os.environ["SCENEFINDER_MINILM_MODEL_PATH"] = (
    "/absolute/path/to/minilm_finetuned/final_model"
)
~~~

Fusion 함수의 주요 입력은 다음과 같습니다.

~~~python
predict_moments_fusion(
    video_id=video_id,
    feature_path=feature_path,
    subtitles=subtitles,
    korean_query=korean_query,
    english_query=english_query,
    video_duration=video_duration,
    subtitle_json_path=subtitle_json_path,
    top_k=5,
    model_type="finetuned",
)
~~~

이는 함수 호출 형식을 보여주는 예시입니다.
위 변수들에는 실제 영상의 값이 필요합니다.

Fusion은 영상 특징을 사용하는 Moment-DETR 검색과
자막 텍스트 의미 검색 후보를 결합합니다.

다만 현재 팀의 실제 검색 API가
이 Fusion 함수를 호출하도록 완전히 연결되었는지는
별도 확인이 필요합니다.

---

## 8. 실행 환경 및 의존성

다음은 실험 코드에서 사용하는 주요 Python 패키지입니다.

~~~text
torch
numpy
sentence-transformers
transformers
datasets
accelerate
faster-whisper
ffmpeg-python
ftfy
regex
tqdm
~~~

정확한 호환 버전은 실행 환경에 맞추어 검증해야 합니다.

기존 Moment-DETR 추론에는
프로젝트 내 별도 모델 코드와 가중치, CLIP 관련 의존성이 필요합니다.

Whisper STT, 영상 feature 추출, MiniLM 실행은
각각 처리 시간과 메모리를 사용하므로
실제 서비스 배포 환경에서 추가 성능 검증이 필요합니다.

---

## 9. 데이터·모델 파일 관리 주의사항

다음 항목은 GitHub에 업로드하지 않습니다.

- AI-Hub에서 제공받은 원본 TAR·ZIP·JSON 데이터
- AI-Hub 원문이 포함된 학습·검증 JSONL
- 대용량 학습 완료 모델 가중치 및 체크포인트
- 라이선스와 공개 가능 여부를 확인하지 않은 영상·자막
- Google Drive 개인 백업 및 임시 파일

GitHub에는 데이터가 아닌
**전처리·학습·평가 코드, 실행 설명, 집계 성능 수치**
중 공유 가능한 항목만 포함합니다.

실제 AI-Hub 자료는 별도 이용 조건과
팀 내 접근 권한을 확인해야 합니다.

---

## 10. 현재 한계와 추후 확인 사항

1. 텍스트 검색 성능 향상이 영상 구간 검색 성능 향상으로
   자동 연결되는 것은 아닙니다.
2. 한국어 질문을 Moment-DETR용 영어 질문으로 변환하는
   과정은 검색 API와의 연결 시 별도 처리해야 합니다.
3. Whisper가 생성한 자막의 품질에 따라
   자막 의미 검색 결과가 달라질 수 있습니다.
4. Fusion과 Consensus 후보 순위 및 최종 시작 시점의
   정확도는 실제 영상 테스트로 추가 검증해야 합니다.
5. 현재 Fusion 함수의 결과 형식과 백엔드 API의
   응답 형식이 완전히 호환되는지 확인해야 합니다.
6. 모델 로드, 영상 feature 생성, Whisper 전사에 따른
   처리 지연 및 서비스 자원 사용량을 점검해야 합니다.

이 문서는 실험과 코드의 재현 방법을 정리한 것으로,
백엔드 통합 완료나 배포 성능 검증을 의미하지 않습니다.
