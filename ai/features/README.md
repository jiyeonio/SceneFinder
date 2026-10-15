# Moment-DETR Feature / Inference Pipeline

SceneFinder 프로젝트에서 자연어 질의에 해당하는 영상 구간을 찾기 위해
Moment-DETR pretrained 모델을 연결한 코드입니다.

현재 단계에서는 모델 학습 자체가 아니라,
pretrained Moment-DETR baseline을 우리 프로젝트 코드에서 직접 실행할 수 있도록
video feature extraction, query feature extraction, 모델 입력 구성, inference pipeline을 구현했습니다.

---

## 1. 전체 흐름

```text
원본 MP4
→ CLIP video feature 추출
→ feature 정규화
→ TEF(Temporal Endpoint Feature) 추가
→ 자연어 query의 CLIP text feature 생성
→ pretrained Moment-DETR inference
→ start_time / end_time / score 반환
```

서비스용 전처리 파이프라인과 Moment-DETR용 feature pipeline은 분리해서 사용합니다.

```text
서비스용 전처리
10초 segment + 5초 overlap
→ segment별 frame 추출
→ subtitle parsing
→ transcript 정렬
→ video_data.json

Moment-DETR 모델용
원본 MP4
→ 2초 간격 CLIP feature
→ TEF
→ query feature
→ Moment-DETR
→ timestamp prediction
```

---

## 2. 폴더 구조

```text
ai/
├── preprocessing/
│   ├── video_metadata.py
│   ├── segment_video.py
│   ├── extract_frames.py
│   ├── parse_subtitle.py
│   ├── align_transcript.py
│   ├── build_video_data.py
│   └── pipeline.py
│
├── features/
│   ├── moment_detr_features.py
│   ├── check_features.py
│   ├── prepare_moment_detr_input.py
│   ├── extract_query_features.py
│   ├── build_moment_detr_inputs.py
│   ├── load_moment_detr_model.py
│   ├── run_moment_detr_inference.py
│   ├── compare_official_inference.py
│   └── README.md
│
└── external/
    └── moment_detr/
```

`ai/external/moment_detr/`는 외부 Moment-DETR repository이므로
현재 프로젝트 GitHub에는 포함하지 않습니다.

---

## 3. External Dependency: Moment-DETR

이 프로젝트는 공개된 Moment-DETR 코드를 외부 dependency로 사용합니다.

Moment-DETR 코드를 프로젝트 내부에 직접 포함해 GitHub에 업로드하지 않고,
각 개발 환경에서 별도로 다운로드한 뒤 아래 경로에 배치합니다.

```text
ai/external/moment_detr/
```

예상 구조는 다음과 같습니다.

```text
ai/
├── external/
│   └── moment_detr/
│       ├── data/
│       ├── moment_detr/
│       ├── res/
│       ├── run_on_video/
│       ├── standalone_eval/
│       ├── utils/
│       ├── README.md
│       └── LICENSE
│
├── features/
└── preprocessing/
```

특히 pretrained checkpoint는 다음 위치에 있어야 합니다.

```text
ai/external/moment_detr/
└── run_on_video/
    └── moment_detr_ckpt/
        └── model_best.ckpt
```

현재 feature 및 inference 코드는 다음 경로를 기준으로 Moment-DETR을 불러옵니다.

```python
MOMENT_DETR_ROOT = Path(
    "ai/external/moment_detr"
)
```

따라서 다른 위치에 Moment-DETR을 배치할 경우
코드 내 `MOMENT_DETR_ROOT` 경로도 함께 수정해야 합니다.

---

## 4. PyTorch 최신 버전 호환성 수정

현재 로컬 환경의 최신 PyTorch에서는 기존 Moment-DETR checkpoint를 불러올 때
`weights_only` 관련 오류가 발생할 수 있습니다.

오류 예시:

```text
_pickle.UnpicklingError:
Weights only load failed.
```

이는 최신 PyTorch에서 `torch.load()`의 기본 동작이 변경되었기 때문입니다.

Moment-DETR의 다음 파일:

```text
ai/external/moment_detr/run_on_video/model_utils.py
```

안의 기존 코드:

```python
ckpt = torch.load(
    ckpt_path,
    map_location="cpu"
)
```

를 다음과 같이 수정하여 사용했습니다.

```python
ckpt = torch.load(
    ckpt_path,
    map_location="cpu",
    weights_only=False
)
```

이 설정은 신뢰할 수 있는 공식 Moment-DETR checkpoint를 사용하는 경우에만 적용합니다.

---

## 5. 주요 Python dependency

현재 로컬 실행 과정에서 사용한 주요 패키지는 다음과 같습니다.

```text
torch
torchvision
torchaudio
opencv-python
ffmpeg-python
ftfy
regex
scipy
pandas
```

필요 시 다음과 같이 설치할 수 있습니다.

```bash
python -m pip install torch torchvision torchaudio
python -m pip install opencv-python
python -m pip install ffmpeg-python
python -m pip install ftfy
python -m pip install regex
python -m pip install scipy
python -m pip install pandas
```

Moment-DETR 및 CLIP의 추가 dependency가 필요한 경우
실행 환경에 맞게 추가 설치합니다.

---

## 6. moment_detr_features.py

원본 MP4 영상에서 CLIP 기반 video feature를 추출합니다.

현재 테스트 영상:

```text
data/raw/test_audio.mp4
```

테스트 영상 길이:

```text
54.32 seconds
```

Moment-DETR 공식 demo와 동일하게 약 2초 단위로 feature를 추출했습니다.

현재 결과:

```text
Video Feature shape:
torch.Size([27, 512])
```

즉,

```text
27개의 video clip
×
512차원 CLIP feature
```

형태입니다.

추출된 feature는 다음 위치에 저장합니다.

```text
data/features/video_001_clip_features.pt
```

`data/features/`는 실행 시 생성되는 결과물이므로
GitHub에는 포함하지 않습니다.

---

## 7. check_features.py

저장된 video feature가 정상적으로 저장되고 다시 불러와지는지 확인합니다.

현재 확인 결과:

```text
Feature 불러오기 성공!
Feature shape: torch.Size([27, 512])
Data type: torch.float32
Device: cpu
```

---

## 8. prepare_moment_detr_input.py

저장된 CLIP video feature를 Moment-DETR 입력 형태로 변환합니다.

먼저 CLIP feature를 정규화합니다.

```text
[27, 512]
```

이후 각 clip의 시간적 위치를 나타내는
TEF(Temporal Endpoint Feature)를 추가합니다.

TEF shape:

```text
[27, 2]
```

최종 video feature:

```text
[27, 514]
```

즉,

```text
512차원 CLIP feature
+
2차원 TEF
=
514차원
```

형태가 됩니다.

---

## 9. extract_query_features.py

자연어 query를 CLIP text encoder를 이용해 feature로 변환합니다.

현재 테스트 query:

```text
the steak is flipped while cooking in the pan
```

현재 결과:

```text
Query Feature shape:
torch.Size([11, 512])
```

즉 해당 query가

```text
11개의 text token feature
×
512차원
```

형태로 변환되었습니다.

---

## 10. build_moment_detr_inputs.py

video feature와 query feature를
Moment-DETR 모델이 실제로 사용하는 입력 구조로 구성합니다.

Moment-DETR 입력 key는 다음 네 개입니다.

```text
src_vid
src_vid_mask
src_txt
src_txt_mask
```

현재 테스트 결과:

```text
src_vid:
torch.Size([1, 27, 514])

src_vid_mask:
torch.Size([1, 27])

src_txt:
torch.Size([1, 11, 512])

src_txt_mask:
torch.Size([1, 11])
```

첫 번째 차원은 batch size입니다.

---

## 11. load_moment_detr_model.py

Moment-DETR pretrained checkpoint를 불러오는 테스트 코드입니다.

사용 checkpoint:

```text
ai/external/moment_detr/
└── run_on_video/
    └── moment_detr_ckpt/
        └── model_best.ckpt
```

현재 결과:

```text
Moment-DETR 모델 로드 성공!

Model type:
<class 'moment_detr.model.MomentDETR'>
```

---

## 12. compare_official_inference.py

Moment-DETR 공식 `MomentDETRPredictor`와
우리 프로젝트에서 구현한 inference 결과를 비교하기 위한 코드입니다.

공식 predictor는 기본 코드에서 모델이 evaluation mode로 명시적으로 전환되지 않아
같은 영상과 같은 query에서도 결과가 달라질 수 있었습니다.

예를 들어 evaluation mode 적용 전에는 동일 query에서
실행할 때마다 상위 예측 구간이 달라지는 현상이 확인되었습니다.

따라서 비교 시 다음 코드를 추가했습니다.

```python
predictor.model.eval()
```

이후 동일 입력에 대해 고정된 결과를 얻었습니다.

공식 Moment-DETR predictor의 최상위 결과:

```text
Start Time: 2.6520
End Time: 19.6021
Score: 0.7591
```

---

## 13. run_moment_detr_inference.py

SceneFinder 프로젝트에서 사용할 최종 inference 함수입니다.

함수:

```python
predict_moment()
```

사용 예시는 다음과 같습니다.

```python
result = predict_moment(
    video_id="video_001",
    video_feature_path=(
        "data/features/"
        "video_001_clip_features.pt"
    ),
    query=(
        "the steak is flipped "
        "while cooking in the pan"
    )
)

print(result)
```

현재 반환 결과:

```python
{
    "video_id": "video_001",
    "query": "the steak is flipped while cooking in the pan",
    "start_time": 2.652,
    "end_time": 19.6021,
    "score": 0.7591
}
```

---

## 14. 공식 Moment-DETR 결과와 우리 코드 비교

evaluation mode 기준 공식 Moment-DETR:

```text
[2.6520, 19.6021, 0.7591]
```

우리 프로젝트의 `predict_moment()` 결과:

```text
start_time = 2.6520
end_time   = 19.6021
score      = 0.7591
```

두 결과가 동일함을 확인했습니다.

즉,

```text
공식 Moment-DETR inference
=
우리 프로젝트 inference wrapper
```

가 동일하게 동작함을 검증했습니다.

---

## 15. 실행 순서

### 1. Video feature 추출

```bash
python ai/features/moment_detr_features.py
```

결과:

```text
data/features/video_001_clip_features.pt
```

---

### 2. 저장된 feature 확인

```bash
python ai/features/check_features.py
```

---

### 3. Moment-DETR용 video input 확인

```bash
python ai/features/prepare_moment_detr_input.py
```

---

### 4. Query feature 확인

```bash
python ai/features/extract_query_features.py
```

---

### 5. 전체 Moment-DETR 입력 shape 확인

```bash
python ai/features/build_moment_detr_inputs.py
```

---

### 6. Pretrained checkpoint load 확인

```bash
python ai/features/load_moment_detr_model.py
```

---

### 7. 최종 inference

```bash
python ai/features/run_moment_detr_inference.py
```

---

### 8. 공식 inference와 비교

```bash
python ai/features/compare_official_inference.py
```

---

## 16. 현재 완료 상태

현재까지 완료된 작업은 다음과 같습니다.

```text
원본 MP4 입력
→ CLIP video feature extraction
→ feature 저장
→ feature 재사용
→ feature normalization
→ TEF 추가
→ query feature extraction
→ Moment-DETR input 구성
→ pretrained checkpoint load
→ inference
→ start_time / end_time / score 반환
→ 공식 Moment-DETR 결과와 동일성 확인
```

따라서 pretrained Moment-DETR baseline을
SceneFinder 프로젝트 코드에서 직접 사용할 수 있는 상태입니다.

---

## 17. 현재 단계에서 하지 않은 작업

현재 feature/inference pipeline에서는
Moment-DETR 모델 자체의 학습은 수행하지 않았습니다.

아직 진행하지 않은 작업:

```text
QVHighlights training
fine-tuning
validation
test evaluation
hyperparameter tuning
best checkpoint selection
Recall@1 평가
mAP 평가
```

이 부분은 모델 학습 담당자가 이어서 진행합니다.

---

## 18. 모델 학습 담당자 다음 단계

다음 단계는 QVHighlights를 이용한
Moment-DETR 모델 학습 및 평가입니다.

예상 흐름:

```text
QVHighlights dataset 준비
→ annotation 확인
→ official feature 준비
→ Dataset / DataLoader 구성
→ scratch training 또는 pretrained checkpoint 기반 fine-tuning
→ validation
→ best checkpoint 선택
→ test evaluation
→ pretrained baseline과 성능 비교
```

QVHighlights annotation의 주요 항목:

```text
query
vid
duration
relevant_windows
relevant_clip_ids
saliency_scores
```

`relevant_windows`는 자연어 query에 대응하는 정답 영상 시간 구간입니다.

평가에는 Moment Retrieval 기준으로
Recall@1 및 mAP 등을 사용할 예정입니다.

---

## 19. 서비스용 전처리와 모델용 feature 구분

중요:

서비스용으로 구현한

```text
10초 segment
+
5초 overlap
+
segment별 3 frames
```

구조를 그대로 Moment-DETR 입력으로 사용하지 않습니다.

서비스용 전처리의 목적:

```text
영상 구조화
자막 정리
segment 관리
frame 관리
video_data.json 생성
```

Moment-DETR feature pipeline의 목적:

```text
원본 MP4
→ 2초 간격 CLIP feature
→ TEF
→ query feature
→ Moment-DETR
```

두 파이프라인은 목적이 다르므로 분리해서 유지합니다.

---

## 20. GitHub 관리 정책

다음 항목은 GitHub에 포함합니다.

```text
ai/preprocessing/
ai/features/
ai/notebooks/
```

다음 항목은 GitHub에 포함하지 않습니다.

```text
ai/external/
data/features/
```

`.gitignore`에 다음 경로를 추가합니다.

```gitignore
ai/external/
data/features/
```

`ai/external/`은 외부 Moment-DETR repository이며,
`data/features/`는 실행 과정에서 생성되는 feature 파일이므로
각 개발 환경에서 별도로 준비하거나 생성합니다.

---

## 21. 현재 최종 상태

현재 SceneFinder pipeline은 다음 단계까지 연결되어 있습니다.

```text
사용자 영상
→ preprocessing
→ Moment-DETR용 feature extraction
→ 자연어 query encoding
→ pretrained Moment-DETR
→ start_time / end_time / score
```

현재까지는 pretrained baseline 연결 및 검증이 완료된 상태이며,
다음 단계에서는 QVHighlights를 활용한 모델 학습 및 정량평가를 진행합니다.