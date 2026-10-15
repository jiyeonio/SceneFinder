# SceneFinder 한국어 AI 검색 및 백엔드 연동 가이드

## 1. 목적

한국어 영상 검색을 위해 개발·실험한 AI 기능과
팀 백엔드 검색 API를 연결할 때 필요한 사항을 정리합니다.

이 문서는 연동 가이드이며,
백엔드 통합이나 서비스 배포가 완료됐다는 의미는 아닙니다.

## 2. 구현된 AI 구성

- Moment-DETR 기반 영상 구간 후보 탐색
- Whisper 기반 음성 전사 및 자막 JSON 생성 코드
- MiniLM 기반 한국어·영어 자막 의미 검색
- 기본 MiniLM / Fine-tuned MiniLM 선택 기능
- 영상·자막 후보를 결합하는 Fusion 검색
- 후보 시간 구간 중첩을 활용하는 Consensus V1·V2

관련 코드:

~~~text
ai/features/run_moment_detr_inference.py
ai/features/fusion_search.py
ai/features/consensus_rerank.py
ai/preprocessing/transcribe_service.py
~~~

MiniLM 실험 코드:

~~~text
ai/experiments/korean_minilm/
├── prepare_data.py
├── train.py
├── evaluate.py
├── README.md
└── results/
    └── full_validation_metrics.json
~~~

## 3. 기존 검색 API와 Fusion 입력 차이

이전 백엔드 코드 점검 당시 검색 API는
Moment-DETR Hybrid 함수를 호출하는 구조였습니다.

기존 주요 입력:

- video_id
- 영상 feature 경로
- 자연어 query
- top_k

Fusion 함수는 다음 입력을 요구합니다.

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

따라서 백엔드 연동 전 다음 값을 확보해야 합니다.

- 한국어 사용자 질의
- Moment-DETR에 전달할 영어 질의
- 검색할 영상의 feature 경로
- 영상 전체 길이
- 해당 영상의 자막 데이터와 자막 JSON 경로
- MiniLM 모델 선택 및 모델 경로

백엔드 코드는 팀원 작업에 따라 변경될 수 있으므로
연동 직전 최신 코드를 다시 확인해야 합니다.

## 4. 한국어 질의 처리

현재 Fusion 함수는 한국어 검색어와 영어 검색어를
별도 인자로 전달받습니다.

예시:

~~~text
korean_query: "두부를 칼로 자르는 장면"
english_query: "the scene where tofu is cut with a knife"
~~~

위 영어 문장은 설명을 위한 번역 예시입니다.

**현재 Fusion 함수에 자동 번역 기능이 내장된 것은 아닙니다.**

실제 서비스에서는 한국어→영어 변환 방식,
번역 실패 처리, 영어 입력 처리 정책을 정해야 합니다.

## 5. Whisper 자막

전사 함수:

~~~python
transcribe_video(
    video_path=video_path,
    video_id=video_id,
)
~~~

자막 저장 위치:

~~~text
<project_root>/data/processed/<video_id>/subtitles.json
~~~

생성 데이터의 예시:

~~~json
[
  {
    "start_time": 1.25,
    "end_time": 3.47,
    "text": "예시 자막입니다."
  }
]
~~~

현재 코드에는 다음 보호 기능이 있습니다.

- 프로젝트 루트 기준 저장 경로
- 기존 자막 JSON 재사용
- 잘못된 video_id 차단
- 기존 자막 파일 덮어쓰기 방지

실제 업로드 영상에서의 전사,
동시 요청, 전사 실패 및 백엔드 연결은 별도로 검증해야 합니다.

## 6. MiniLM 모델 선택

기본 모델:

~~~text
sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
~~~

Fine-tuned 모델 경로 지정:

~~~python
import os

os.environ["SCENEFINDER_MINILM_MODEL_PATH"] = (
    "/absolute/path/to/final_model"
)
~~~

선택 옵션:

- `model_type="base"`: 기본 MiniLM
- `model_type="finetuned"`: 추가 학습한 MiniLM

Colab에서 두 모델의 로드 및
384차원 한국어 문장 임베딩 생성을 확인했습니다.

이는 모델 선택 기능 테스트 결과이며,
백엔드 통합이나 최종 영상 검색 성능 검증은 아닙니다.

## 7. Fusion 결과와 백엔드 응답 형식

이전 검색 API에서는 다음 필드를 사용했습니다.

~~~text
segment_id
start_time
end_time
score
~~~

Fusion의 자막 기반 결과에는
`score=None`인 후보가 존재할 수 있습니다.

자막 검색 유사도는
`subtitle_score`에 담길 수 있습니다.

따라서 백엔드에서 다음처럼 계산하면
오류가 발생할 수 있습니다.

~~~python
max(moment["score"] for moment in moments)
~~~

연동 시 주의사항:

1. Fusion 결과의 필드 구조 확인
2. score=None인 후보의 안전한 처리
3. Moment-DETR 점수와 MiniLM 유사도 구분
4. 최종 순위 및 Top-1 선정 규칙 결정
5. 기존 프론트엔드 응답 형식 유지

서로 다른 점수를 검증 없이
같은 확률이나 동일한 의미의 점수로 취급하면 안 됩니다.

## 8. Consensus V1·V2

구현 코드:

~~~text
ai/features/consensus_rerank.py
~~~

Moment-DETR Hybrid, 한국어 자막 검색,
영어 자막 검색 후보 간 시간 구간 중첩을 활용합니다.

- V1: 후보 간 IoU를 순위 점수에 추가
- V2: IoU 0.5 이상인 중첩을 점수에 추가

Consensus는 현재 실험 기능입니다.

최종 서비스에 사용할 방식은
실제 영상의 Top-1 검색 정확도를 비교해 결정해야 합니다.

## 9. MiniLM 평가 결과

AI-Hub Validation 텍스트 쌍 1,948개 평가:

| 지표 | 기본 MiniLM | Fine-tuned MiniLM |
|---|---:|---:|
| Recall@1 | 51.03% | 75.15% |
| Recall@5 | 65.55% | 85.88% |
| MRR | 0.5773 | 0.7996 |

세부 결과:

~~~text
ai/experiments/korean_minilm/results/full_validation_metrics.json
~~~

위 값은 **한국어 요약문→대화문 텍스트 검색 성능**입니다.

영상 구간 검색의 R1@0.5, mAP, IoU와는 구별해야 합니다.

## 10. 서비스 연동 전 확인할 항목

- [ ] 최신 백엔드 검색 API 확인
- [ ] Fusion 호출에 필요한 입력값 확보
- [ ] 한국어→영어 질의 처리
- [ ] 자막 입력 형식 검증
- [ ] feature 경로 및 영상 길이 확인
- [ ] score=None 처리
- [ ] 프론트엔드 검색 결과 스키마 유지
- [ ] Whisper 실제 영상 전사 테스트
- [ ] 기본/Fine-tuned MiniLM 영상 검색 비교
- [ ] 처리 속도 및 메모리 측정
- [ ] 배포 환경의 라이브러리·모델 경로 확인

## 11. 데이터 및 코드 공유 주의사항

GitHub에 포함하지 않을 항목:

- AI-Hub 원본 TAR·ZIP·JSON
- 실제 AI-Hub 문장이 포함된 학습·검증 JSONL
- 대용량 모델 가중치 및 체크포인트
- 공개 권한을 확인하지 않은 영상 및 자막
- 개인 Google Drive 백업

GitHub에는 공유 가능한 코드와 설명,
개별 원문이 없는 집계 평가 결과만 포함합니다.

## 12. 현재 완료 범위

완료 또는 확인한 내용:

- Fusion 및 Consensus 코드 복구
- 기본/Fine-tuned MiniLM 모델 로드 검증
- Whisper 서비스 코드 복구
- MiniLM 전처리·학습·평가 코드 복구
- 전체 Validation 평가 결과 복구
- 재현 절차와 연동 요구사항 문서화

아직 완료되지 않은 내용:

- 최신 검색 API와 Fusion의 실제 연결
- 실제 업로드 영상 전체 흐름 검증
- 배포 서버에서의 모델·Whisper 실행 검증
- Fine-tuned 모델의 영상 구간 검색 개선 입증
- 최종 Top-1 정확도 및 지연 시간 검증
