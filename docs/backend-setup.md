# 백엔드 로컬 실행 가이드

> 기준: Python 3.10 / NVIDIA GPU(CUDA 12.6) 권장 (Linux, macOS, Windows Git Bash)

## 0. 준비물
- Python 3.10, Git, [ffmpeg](https://ffmpeg.org) (`ffmpeg -version`이 되어야 함)
- Node.js 20 이상 (`node -v`가 되어야 함) — yt-dlp가 YouTube 영상을 받을 때 JS 런타임으로 사용합니다. 서버를 실행하는 터미널의 PATH에 있어야 합니다.
- Supabase 프로젝트 키, YouTube Data API 키 (각 서비스 콘솔에서 발급)
- MiniLM `final_model` 폴더 (한국어 자막 검색용, 아래 3번)

## 1. 소스 코드와 가상환경
소스 코드를 받습니다:

    git clone https://github.com/jiyeonio/SceneFinder.git
    cd SceneFinder

프로젝트 루트에서 가상환경을 만듭니다:

    python -m venv .venv
    source .venv/bin/activate           # Windows(Git Bash): source .venv/Scripts/activate

GPU가 있으면 torch를 먼저 설치:

    pip install torch==2.14.1 torchvision==0.29.1 --index-url https://download.pytorch.org/whl/cu126

(GPU가 없으면: `pip install torch torchvision`)

그 다음:

    pip install -r backend/requirements.txt

## 2. 환경변수
`backend/.env.example`을 복사해서 `backend/.env`를 만들고 값을 채웁니다. (`.env`는 절대 커밋하지 마세요)

    cp backend/.env.example backend/.env

주요 항목:
- `USE_REAL_AI=1` : 실제 AI 사용 (0이면 가짜 결과로 동작해서 검색이 의미 없음)
- `SCENEFINDER_MINILM_MODEL_PATH` : 아래 3번에서 준비한 MiniLM 폴더의 절대 경로

## 3. 모델 파일
학습된 모델 가중치는 용량이 커서 저장소에 포함하지 않습니다. 모델 파일은 아래 위치에 배치하세요.

### MiniLM (한국어 자막 검색)
한국어 자막 검색은 한국어 데이터로 파인튜닝한 MiniLM(`final_model`)을 사용합니다.
학습 방법은 `ai/experiments/korean_minilm/`을 참고하세요.

모델 폴더는 프로젝트 폴더 밖의 영구 경로(예: `/path/to/models/minilm_ko`)에 둡니다.
폴더 안에 `model.safetensors`(약 449MB), `config.json`, `tokenizer.json`, `modules.json`, `1_Pooling/`이 모두 있어야 합니다.
그다음 `backend/.env`의 `SCENEFINDER_MINILM_MODEL_PATH`에 그 폴더의 절대 경로를 적습니다. (예: `/path/to/models/minilm_ko`)

로드 확인 (가상환경 켠 상태):

    python -c "from sentence_transformers import SentenceTransformer as S; m=S('/path/to/models/minilm_ko'); print(m.encode(['테스트']).shape)"

`(1, 384)`가 나오면 정상입니다.

### Moment-DETR 체크포인트 (자막 없는 영상의 영상 검색)
`models/moment_detr/scratch_clip_align_best.ckpt` 위치(프로젝트 루트 기준)에 둡니다.
없으면 자막이 없는 영상은 검색 결과가 나오지 않습니다.

## 4. 서버 실행
프로젝트 루트에서 (가상환경 켠 상태):

    uvicorn backend.main:app --reload

`Application startup complete`가 보이면 완료.
- API 문서/테스트: http://127.0.0.1:8000/docs
- 첫 실행은 모델을 내려받고 올리느라 시간이 걸립니다. 이후 검색은 빠릅니다.
- `/docs`에서는 `Authorization` 헤더가 전달되지 않아 로그인이 필요한 API는 curl이나 프론트에서 확인하세요.

## 5. 동작 방식 요약
1. 유튜브 영상을 검색해서 `POST /api/search`로 질문하면, 처음 보는 영상은 분석을 시작합니다 (202 PROCESSING).
2. 분석 = 영상 다운로드 → 한국어 음성 자막 생성(Whisper) → 한국어 자막이 없을 때만 CLIP 영상 특징 추출 → 저장.
3. 분석이 끝나면(INDEXED) 같은 요청에 구간 결과가 나옵니다.
4. 한국어 자막이 있으면 자막 검색(MiniLM)으로 구간을 찾고, 자막이 없으면 검색어를 영어로 번역해 영상 검색(Moment-DETR)으로 찾습니다.
5. 분석 상태 확인: `GET /api/videos/youtube/{id}/status`
6. 분석 결과(자막·특징 파일)는 서버를 실행한 컴퓨터에 저장됩니다. DB에 분석 기록이 있어도 그 컴퓨터에 파일이 없으면 다시 분석합니다.

자세한 API는 `docs/api-spec.md`를 참고하세요.

## 6. 자주 나는 문제
| 증상 | 해결 |
|---|---|
| `uvicorn: command not found`, `No module named 'torch'` | 가상환경이 꺼져 있음. `source .venv/bin/activate` |
| `supabase_url is required` | `backend/.env`가 없거나 값이 비어 있음 |
| `ffmpeg not found` | ffmpeg 설치 후 PATH 등록, 터미널 재시작 |
| 검색 결과가 이상하거나 항상 같은 값 | `USE_REAL_AI=1`인지 확인 |
| 한국어 영상인데 자막 검색이 안 됨 | `data/processed/subtitles/{영상ID}.json` 존재 여부 확인. 없으면 `python -m backend.services.indexer subs {영상ID}` |
| MiniLM 로드 실패 | `SCENEFINDER_MINILM_MODEL_PATH` 폴더에 `config.json`, `1_Pooling` 등 설정 파일이 있는지 확인 |
| 프론트에서 CORS 에러 | `backend/.env`의 `CORS_ORIGINS`에 프론트 주소 추가 후 서버 재시작 |
| 영상 다운로드 실패, "No supported JavaScript runtime" 경고 | 서버 터미널에서 `node -v` 확인, `pip install -U -r backend/requirements.txt`로 yt-dlp 갱신 |
| "YouTube에서 일시적으로 영상 다운로드를 제한했어요" | YouTube의 일시적 다운로드 제한. `DOWNLOAD_BLOCK_COOLDOWN_MIN`(기본 10분) 동안은 같은 영상을 다시 받지 않으니 잠시 후 다시 시도 |
| 로그인 직후 인증 에러 | Supabase 대시보드에서 Confirm email이 꺼져 있는지 확인 |

## 7. 지금 알려진 제한
- 영상 길이 30분 초과는 분석하지 않습니다 (`TOO_LONG`).
- 유튜브 검색 API는 하루 호출 한도가 있습니다 (검색 1회 = 100 units, 하루 10,000).
- 영상 분석은 GPU 서버가 필요해서, 클라우드 배포 없이 로컬 서버로 실행합니다.
