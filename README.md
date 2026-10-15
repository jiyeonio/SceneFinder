# SceneFinder

자연어로 영상 속 장면을 찾아주는 멀티모달 영상 구간 검색 서비스

## 프로젝트 소개

SceneFinder는 "고기를 볶는 장면"처럼 찾고 싶은 장면을 문장으로 입력하면, YouTube 영상을 검색하고 각 영상 안에서 그 내용과 가장 관련 있는 구간을 찾아 해당 시점부터 바로 재생해 주는 웹 서비스입니다.

영상에 한국어 음성이 있으면 음성을 자막으로 바꿔 문장 의미로 검색하고, 음성이 없는 영상은 화면 내용을 분석하는 영상-텍스트 모델로 검색합니다.

검색 흐름:

    한국어 검색어
      ├─ 영상에 한국어 자막(Whisper)이 있으면
      │    → 한국어 데이터로 파인튜닝한 MiniLM으로 자막 의미 검색 → 구간(timestamp)
      └─ 한국어 자막이 없으면
           → 검색어를 영어로 번역 → Moment-DETR(CLIP 영상 특징) 영상 검색 → 구간(timestamp)

- 한국어 자막이 있는 영상은 영상 특징 추출을 생략해 분석 시간을 줄였습니다.
- 자막 또는 영상 특징 중 하나만 있어도 검색할 수 있습니다.

## 주요 기능

- **자연어 장면 검색**: 검색어로 YouTube 영상을 찾고, 영상마다 관련 구간과 관련도 점수를 보여줍니다.
- **검색 결과 즉시 표시**: YouTube 검색 결과를 바로 카드로 보여주고, 영상별 분석 상태(확인 중 / 분석 전 / 분석 중 / 완료 / 결과 없음 / 실패)를 실시간으로 갱신합니다.
- **필요한 만큼만 분석**: 검색 1번당 상위 몇 개 영상만 자동 분석하고, 나머지는 카드를 눌렀을 때 분석합니다. 이미 분석한 영상은 다시 내려받지 않습니다.
- **구간 재생**: 결과를 누르면 YouTube 플레이어가 해당 시점부터 재생합니다. 한 영상의 여러 구간을 타임라인 마커와 시간 칩으로 보여주고, 이전/다음 구간으로 이동할 수 있습니다.
- **분석 대기 화면**: 아직 분석되지 않은 영상을 누르면 분석 상태를 보여주다가, 끝나면 가장 관련 있는 구간부터 자동 재생합니다.
- **계정 기능**: 회원가입/로그인, 마음에 드는 구간 저장(라이브러리), 검색 기록
- **다운로드 제한 대응**: YouTube가 영상 다운로드를 일시적으로 막으면 사용자에게 한국어 안내를 보여주고, 일정 시간 동안 같은 영상을 다시 내려받지 않습니다.

## 구조

    .
    ├── frontend/                 # 웹 UI (React + Vite)
    │   └── src/
    │       ├── components/       # 검색 목록, 플레이어, 분석 화면, 로그인, 라이브러리
    │       ├── services/         # 백엔드 API 호출 (searchApi.ts)
    │       └── utils/            # 카드 상태·정렬, 시간 표시
    ├── backend/                  # API 서버 (FastAPI)
    │   ├── main.py               # 인증, 즐겨찾기, 검색 기록 API
    │   └── services/
    │       ├── search_api.py     # YouTube 검색, 영상 분석 요청, 장면 검색 API
    │       ├── indexer.py        # 분석 파이프라인 (다운로드 → 자막 → 필요 시 영상 특징)
    │       ├── acquire.py        # 영상 다운로드 (yt-dlp)
    │       ├── subtitles.py      # 음성 → 자막 (faster-whisper)
    │       ├── translate.py      # 검색어 한→영 번역
    │       └── youtube_search.py # YouTube Data API
    ├── ai/
    │   ├── features/             # 자막 의미 검색(MiniLM), Moment-DETR 영상 특징·추론
    │   ├── experiments/          # 한국어 MiniLM 학습·평가 코드와 실험 결과
    │   └── vendor/moment_detr/   # Moment-DETR 원본 코드 (MIT License)
    ├── docs/                     # API 명세, 백엔드 상세 설정
    ├── requirements.txt          # AI 실험용 패키지
    └── backend/requirements.txt  # 서버 실행용 패키지

### 기술 스택

| 구분 | 사용 기술 |
|---|---|
| Frontend | React 19, TypeScript, Vite 6, Tailwind CSS 4, YouTube IFrame Player API |
| Backend | FastAPI, Supabase (PostgreSQL, Auth), YouTube Data API, yt-dlp |
| AI | PyTorch, faster-whisper, sentence-transformers (MiniLM 파인튜닝), Moment-DETR, CLIP, NLLB 번역 모델 |

## 실행 방법

백엔드(FastAPI, 8000 포트)와 프론트엔드(Vite, 3000 포트)를 각각 실행합니다.
GPU, 모델 준비 등 백엔드 상세 설정은 [docs/backend-setup.md](docs/backend-setup.md)를 참고하세요.

### 준비물

- Python 3.10 이상, ffmpeg
- Node.js 20 이상 (`node -v`로 확인) — 프론트엔드 실행과 백엔드의 YouTube 영상 다운로드(yt-dlp)에 모두 필요
- Supabase 프로젝트 키, YouTube Data API 키

### 모델 파일

학습된 모델 가중치는 용량이 커서 저장소에 포함하지 않습니다.

- **한국어 MiniLM**: 자막 의미 검색에 사용합니다. 모델 폴더를 준비한 뒤 `backend/.env`의 `SCENEFINDER_MINILM_MODEL_PATH`에 경로를 적습니다. 학습 방법은 [ai/experiments/korean_minilm/](ai/experiments/korean_minilm/)에 있습니다.
- **Moment-DETR 체크포인트**: 자막이 없는 영상의 영상 기반 검색에 사용합니다. `models/moment_detr/scratch_clip_align_best.ckpt` 위치에 둡니다. 없으면 자막이 없는 영상은 검색 결과가 나오지 않습니다.

### 백엔드

프로젝트 루트에서:

    python -m venv .venv
    source .venv/bin/activate              # Windows(Git Bash): source .venv/Scripts/activate
    pip install -r backend/requirements.txt
    cp backend/.env.example backend/.env   # 값을 채우고, 절대 커밋하지 마세요
    uvicorn backend.main:app --host 0.0.0.0 --port 8000

- 백엔드를 실행하는 터미널에서 `node -v`가 동작해야 합니다. yt-dlp가 YouTube 영상을 받을 때 node를 JS 런타임으로 사용하며, 없으면 "No supported JavaScript runtime" 경고와 함께 다운로드가 실패할 수 있습니다.
- Node.js를 PATH에 없는 위치에 설치했다면 실행할 때 경로를 붙여 주세요.

      PATH=/path/to/node/bin:$PATH uvicorn backend.main:app --host 0.0.0.0 --port 8000

- 실행 후 http://localhost:8000/docs 에서 API를 확인할 수 있습니다.

### 프론트엔드

    cd frontend
    npm install
    cp .env.example .env
    npm run dev                            # http://localhost:3000

## 환경변수

`backend/.env` (`backend/.env.example` 참고)

| 변수 | 필수 | 설명 |
|---|---|---|
| `SUPABASE_URL`, `SUPABASE_SERVICE_KEY` | 필수 | Supabase 접속 정보. 서비스 키는 백엔드에만 두고 프론트엔드에 넣지 마세요 |
| `YOUTUBE_API_KEY` | 필수 | YouTube Data API 키 (영상 검색, 영상 길이 조회) |
| `USE_REAL_AI` | 필수 | `1`이면 실제 AI 모델 사용, `0`이면 가짜 결과로 동작 |
| `SCENEFINDER_MINILM_MODEL_PATH` | 필수 | 한국어 자막 검색용 MiniLM 모델 폴더의 절대 경로 |
| `CORS_ORIGINS` | 선택 | 허용할 프론트엔드 주소 (쉼표로 구분). 비우면 `localhost`/`127.0.0.1`의 3000, 5173 포트 |
| `DOWNLOAD_BLOCK_COOLDOWN_MIN` | 선택 | 기본 `10`. YouTube가 다운로드를 막아(봇 확인, 403 등) 분석에 실패한 영상은 이 시간(분) 동안 다시 받지 않고 "잠시 후 다시 시도해주세요" 안내만 돌려줍니다. 제한이 걸린 상태에서 요청이 더 쌓이지 않게 하기 위한 값이며, `0`이면 끕니다 |
| `TRANSLATE_MODEL`, `SUBTITLE_PAD_BEFORE`, `SUBTITLE_MIN_LEN` | 선택 | 검색어 번역 모델, 자막 구간 보정값 (`.env.example`의 설명 참고) |

`frontend/.env` (`frontend/.env.example` 참고)

| 변수 | 기본값 | 설명 |
|---|---|---|
| `VITE_API_BASE_URL` | `http://127.0.0.1:8000` | 백엔드 주소 |
| `VITE_AUTO_ANALYZE_COUNT` | `5` | 검색 1번당 자동으로 분석을 시작할 영상 수 (`0`~`5`). 나머지 영상은 "분석 전"으로 표시되고, 카드를 눌렀을 때만 분석합니다. 영상 분석마다 YouTube 다운로드가 일어나므로 작게 유지하세요. 백엔드도 요청 1번당 최대 5개로 제한합니다 |

- `VITE_`로 시작하는 값은 브라우저에 그대로 노출되므로 비밀값을 넣으면 안 됩니다.
- `.env`를 바꾼 뒤에는 백엔드와 프론트엔드를 다시 실행해야 적용됩니다.
