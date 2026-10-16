# 서비스 Whisper를 small → large-v3-turbo로 바꾸는 방안

자막 검색 정확도가 오르는지는 [eval_v2.md](eval_v2.md)의 「Whisper」 절에서 확인했고, 이 문서는 서비스에 적용할 때의
**수정 위치, 영상 1개당 처리 시간, GPU 메모리**를 실측해 정리합니다. **코드는 아직 바꾸지 않았습니다.**

## 요약

| 항목 | small (현재) | large-v3-turbo | 변화 |
|---|---|---|---|
| 자막 검색(d), S 질의 IoU ≥ 0.3 (평가셋 v2, 30개) | 27% (8/30) | 43% (13/30) | +16%p (dev 5→7, test 3→6) |
| 자막 생성 시간, 영상 8개 합계 (54분 분량) | 78.7초 | 56.6초 | **약 28% 빠름** |
| 말 많은 영상 1개당 (6~15분) | 9.4~19.9초 | 8.3~16.9초 | 1~11초 단축 |
| 말 없는 영상 1개당 | 0.6~1.7초 | 0.7~1.8초 | 거의 같음 |
| GPU 메모리 (모델 로딩 후 / 최대) | 789 / 1,191 MiB | 2,165 / 2,439 MiB | **약 +1.2~1.4 GiB** |
| 모델 로딩 | 1.6초 | 3.2초 | 서버 시작 때 한 번 |
| 모델 파일 (처음 한 번 내려받음) | 464MB | 1.6GB | |

- large-v3-turbo는 디코더 층이 4개뿐이라, 크기는 small보다 크지만 GPU에서는 같거나 더 빠릅니다. 실측에서 말 많은 영상은 모두 더 빨랐습니다.
- 서비스의 영상 분석 시간은 다운로드 + 자막 생성 (+ 한국어 자막이 없으면 영상 feature)이라, 바뀌는 것은 자막 생성 단계뿐입니다.
- 메모리는 늘어납니다. 같은 GPU에 MiniLM·CLIP·Moment-DETR·번역 모델이 함께 올라가므로, 운영 GPU의 여유 메모리를 먼저 확인해야 합니다.

## 실측: 영상별 자막 생성 시간

서비스와 같은 함수(`backend/services/subtitles.py`의 `_transcribe`, beam 5, VAD)로 GPU(float16)에서 쟀습니다. 모델마다 새 프로세스에서
로딩한 뒤 20초 구간으로 한 번 워밍업하고 영상마다 한 번씩 돌렸습니다.

| 영상 | 길이 | small | large-v3-turbo | 차이 | 문장 수 (small → turbo) |
|---|---|---|---|---|---|
| tofu_silent (말 없음) | 2:39 | 0.6초 (292배속) | 0.7초 (242배속) | +0.1초 | 0 → 0 |
| ag_final | 3:00 | 6.6초 (27배속) | 4.2초 (42배속) | -2.3초 | 59 → 54 |
| tofu_braise | 3:26 | 7.5초 (28배속) | 4.9초 (42배속) | -2.6초 | 48 → 81 |
| airpods_review | 6:05 | 9.4초 (39배속) | 8.3초 (44배속) | -1.2초 | 133 → 127 |
| eggroll_paik | 7:51 | 19.9초 (24배속) | 9.0초 (52배속) | -10.9초 | 221 → 148 |
| mukbang_chicken (말 거의 없음) | 7:53 | 1.7초 (273배속) | 1.8초 (262배속) | +0.1초 | 3 → 4 |
| room_vlog | 8:45 | 13.8초 (38배속) | 10.8초 (49배속) | -3.0초 | 173 → 175 |
| battery_lecture | 15:00 | 19.1초 (47배속) | 16.9초 (53배속) | -2.2초 | 253 → 229 |

- 같은 측정을 한 번 더 했을 때 합계는 small 74.3초 / turbo 53.5초로 비슷했습니다. 다만 small은 같은 영상도 실행마다 문장 수가 조금 달랐습니다
  (ag_final 56·59개). GPU 연산의 작은 차이가 beam search 결과를 바꾸는 것으로 보입니다.
- GPU 메모리는 다른 GPU 작업이 없을 때 GPU 전체 사용량의 증가분으로 쟀습니다(컨테이너에서는 프로세스별 사용량이 보이지 않음).
  CUDA 초기화분이 포함된 값입니다.
- 환경: NVIDIA RTX A5000, faster-whisper 1.2.1. 측정 스크립트: `ai/experiments/whisper_bench/bench.py`,
  결과: `~/scenefinder_eval/whisper_bench/bench.json`(저장소 밖).

## 수정 위치 (확인 후 진행)

### 1. 모델 이름 — 코드 수정 없이도 가능

`backend/services/subtitles.py:17`

    WHISPER_MODEL_SIZE = os.getenv("WHISPER_MODEL_SIZE", "small")

- **방안 A (코드 수정 없음):** 서버의 `backend/.env`에 `WHISPER_MODEL_SIZE=large-v3-turbo`만 추가. 되돌리기 쉽습니다.
- **방안 B (기본값 변경):** 위 줄의 기본값을 `"large-v3-turbo"`로 바꿈. 새로 설치하는 사람도 같은 모델을 쓰게 됩니다.
- 어느 쪽이든 `backend/.env.example`과 README의 환경변수 표에 `WHISPER_MODEL_SIZE`를 추가해야 합니다(지금은 문서에 없음).

### 2. GPU 라이브러리 로딩 — 같이 고치기를 권장

Linux에서 faster-whisper(ctranslate2)는 torch가 먼저 불러온 CUDA 라이브러리(`libcublas.so.12`)를 써야 GPU에서 돕니다. 이 서버에서
torch를 불러오지 않고 Whisper만 실행하면 `Library libcublas.so.12 is not found`로 **조용히 CPU로 넘어갑니다**(직접 확인).
지금 서비스가 GPU로 도는 것은 시작할 때 `warmup_ai()`가 MiniLM을 올리면서 torch를 먼저 불러오기 때문입니다.

- 수정 위치: `backend/services/subtitles.py`의 `_add_torch_dll_dir()`. 지금은 Windows(`os.name == "nt"`)에서만 동작하므로,
  Linux에서도 `import torch`를 먼저 하도록 바꾸면 warmup 순서와 상관없이 GPU를 씁니다.
- CPU로 넘어가면 small도 3~8배속(실측: 3분 영상 62~80초)으로 느려지고, turbo는 그보다 더 느릴 것으로 예상합니다(CPU에서는 재지 않음).
  turbo로 바꾸기 전에 이 부분을 먼저 막는 것이 안전합니다.

### 3. 문서·운영

- `docs/backend-setup.md`: 처음 실행할 때 모델(1.6GB)을 내려받는다는 안내, GPU 메모리 요구량.
- 이미 분석한 영상 226개의 자막(`data/processed/subtitles/`)은 small로 만든 것이고 그대로 쓰입니다. 다시 만들려면 영상을 다시 받아야 해서
  (YouTube 다운로드 제한) **새로 분석하는 영상부터 turbo를 적용**하는 것을 권장합니다. 섞여 있는 상태를 구분하려면 자막 JSON에
  모델 이름을 함께 저장하는 수정이 필요합니다(선택).
- 말이 거의 없는 영상의 판정(`MIN_SUBTITLE_SEGMENTS`, `MIN_SUBTITLE_CHARS`)은 그대로 둡니다. turbo는 문장을 더 길게 묶는 경향이 있어
  (eggroll_paik 221 → 148문장) 기준 근처의 영상은 판정이 바뀔 수 있습니다.

## 권장 순서

1. `subtitles.py`의 torch 선로딩 수정 (CPU로 조용히 넘어가는 문제 방지)
2. `.env`로 turbo 적용(방안 A) → 운영 GPU 메모리 확인
3. 문제없으면 기본값·`.env.example`·README 반영(방안 B)

## 재현 방법

    python ai/experiments/whisper_bench/bench.py --models small,large-v3-turbo --out ~/scenefinder_eval/whisper_bench/bench.json \
        ~/scenefinder_eval/videos/9fmd1LOTa-E.mp4 ~/scenefinder_eval/videos/iSHVe7ozhEk.mp4 ...

다른 GPU 작업이 없을 때 실행해야 GPU 메모리 값이 맞습니다.
