# Supabase를 새 프로젝트로 옮기기

팀 Supabase 프로젝트에서 새 프로젝트(서울 리전)로 옮기는 방법입니다. **영상 분석 상태(videos, video_features)만 옮기고**
회원·검색 기록·즐겨찾기는 옮기지 않습니다. 새 프로젝트에서는 회원가입을 새로 해야 합니다.

| 파일 | 내용 |
|---|---|
| [schema.sql](schema.sql) | 새 프로젝트 SQL Editor에 붙여넣어 실행할 스키마 |
| `tools/supabase/analysis_state.py` | 분석 상태 테이블 export(팀 DB, 읽기만) / import(새 DB) |
| `tools/supabase/use_env.sh` | `backend/.env`를 팀 DB용·내 DB용으로 바꾸기 |

## 1. 권한 확인 결과

| 확인 | 결과 |
|---|---|
| 백엔드가 쓰는 키 | **`SUPABASE_SERVICE_KEY`(service_role)만** 씁니다. `backend/main.py:14-18`, `backend/services/indexer.py:59` |
| anon 키 | 코드·`.env.example` 어디에도 없음 |
| 사용자 토큰 | DB 접근에는 쓰지 않습니다. 로그인 사용자 확인(`auth.get_user(token)`, `main.py`의 `get_current_user`)에만 쓰고, 검색 기록·즐겨찾기는 코드가 `user_id`로 걸러서 service_role로 읽고 씁니다 |
| Auth 호출 | 가입(`sign_up`)·로그인(`sign_in_with_password`)·토큰 확인도 service_role 키로 만든 클라이언트로 합니다 |
| 프론트엔드 | Supabase를 직접 쓰지 않습니다(`frontend/src`에 Supabase 클라이언트·키 없음). 모든 요청이 백엔드를 거칩니다 |

**권장안**

- **RLS: 모든 테이블에 켜고 정책은 만들지 않기** (schema.sql에 포함). service_role은 RLS를 거치지 않으므로 서비스는 그대로 동작하고,
  혹시 anon·authenticated 키가 새어도 Data API로 테이블을 읽거나 쓸 수 없습니다.
- **Data API: 켜 둠**, 노출 스키마는 `public`만. 백엔드의 supabase-py가 Data API(PostgREST)로 DB에 접근하므로 끄면 서비스가 멈춥니다.
- 더 막고 싶으면(선택) 새 프로젝트 SQL Editor에서 anon·authenticated의 테이블 권한을 회수합니다. service_role에는 영향이 없습니다.

      revoke all on public.videos, public.video_features, public.search_history, public.favorites from anon, authenticated;

- service_role 키는 `backend/.env`(서버)에만 둡니다. 프론트엔드 `VITE_*` 변수에 넣으면 브라우저에 그대로 노출됩니다.

## 2. 바꿔야 할 변수

`backend/.env`의 **두 개만** 바꾸면 됩니다. 나머지(YouTube 키, 모델 경로, Whisper 등)는 그대로입니다. 프론트엔드 `.env`에는 Supabase 변수가 없습니다.

| 변수 | 넣을 값 (새 프로젝트 대시보드) |
|---|---|
| `SUPABASE_URL` | Project Settings → API의 Project URL |
| `SUPABASE_SERVICE_KEY` | Project Settings → API Keys의 service_role 키 (secret) |

## 3. 팀 DB용·내 DB용 .env를 같이 두고 바꾸기

`backend/.env`는 백엔드가 직접 읽는 파일이라, 두 벌을 따로 두고 필요한 쪽을 `backend/.env`로 복사합니다(코드 수정 없음).

    bash tools/supabase/use_env.sh init     # 처음 한 번: 지금 backend/.env(팀 DB)를 backend/.env.team으로 복사
    cp backend/.env.team backend/.env.new   # 내 DB용을 만들고, 편집기로 SUPABASE_URL·SUPABASE_SERVICE_KEY 두 줄만 새 값으로 바꿈
    bash tools/supabase/use_env.sh new      # backend/.env ← .env.new (이전 값은 backend/.env.bak)
    bash tools/supabase/use_env.sh team     # 팀 DB로 되돌리기
    bash tools/supabase/use_env.sh status   # 지금 어느 쪽인지 (값은 출력하지 않고 해시로 비교)

- 바꾼 뒤에는 백엔드를 다시 시작해야 적용됩니다.
- `.env.team`·`.env.new`·`.env.bak`은 `.gitignore`(`.env.*`, `*.bak`)로 커밋되지 않습니다. 파일 권한은 600으로 둡니다.

## 4. 데이터 옮기는 순서

1. 새 프로젝트 SQL Editor에서 [schema.sql](schema.sql) 실행 (아래 체크리스트 5-2). 빈 프로젝트에 한 번만 실행하는 SQL입니다(다시 실행하면 `create table`에서 멈춤).
2. 내보내기(팀 DB에서 읽기만, 레포 밖에 저장):

       python tools/supabase/analysis_state.py export        # 기본 저장 위치 ~/scenefinder_supabase_export/<시각>/

3. `backend/.env.new` 준비(3번 절). 
4. 확인(dry-run, 새 DB에 쓰지 않음): 파일 검사(중복, 외래키), 새 DB가 팀 DB와 다른지 확인

       python tools/supabase/analysis_state.py import --in ~/scenefinder_supabase_export/<시각>

5. 가져오기: `--apply`. 끝나면 출력되는 `setval(...)` SQL을 새 프로젝트 SQL Editor에서 실행(video_features.id 번호 이어 붙이기)

       python tools/supabase/analysis_state.py import --in ~/scenefinder_supabase_export/<시각> --apply

6. `bash tools/supabase/use_env.sh new` → 백엔드 재시작 → 확인
   - `GET /api/videos/youtube/<분석된 영상 ID>/status`가 `INDEXED`
   - `POST /api/search`로 그 영상 검색 결과가 나오는지
   - 회원가입 → 로그인 → 즐겨찾기 추가·조회

- 2026-10-16 기준 팀 DB: videos 498행(INDEXED 365, PENDING 75, FAILED 55, PROCESSING 3), video_features 110행.
  분석 중(PROCESSING)이던 3개는 PENDING으로 바꿔 넣어, 다음 검색 때 다시 분석됩니다.
- **feature·자막 파일은 DB에 없습니다.** `data/features`, `data/processed/subtitles`(서버 디스크)에 있고 DB에는 경로만 있습니다.
  같은 서버에서 쓰면 그대로 동작합니다. video_features 110행 중 7행은 절대경로라 다른 컴퓨터의 경로일 수 있고, 파일이 없으면
  그 영상은 검색 결과에서 빠집니다(`_feature_ready`).
- 팀 DB는 그대로 남습니다. 팀원은 계속 팀 DB를 쓰고, 이후 새로 분석한 결과는 두 DB 사이에 자동으로 맞춰지지 않습니다.

## 5. 대시보드 체크리스트

### 5-1. 프로젝트

- [ ] New project → Region: **Northeast Asia (Seoul)**. Database password는 비밀번호 관리자에 저장(코드에서는 쓰지 않음)

### 5-2. 스키마

- [ ] 왼쪽 메뉴 **SQL Editor** → New query → `docs/supabase/schema.sql` 전체 붙여넣기 → Run
- [ ] **Table Editor**에서 videos, video_features, search_history, favorites 4개 테이블, 각 테이블 RLS 「enabled」 확인
- [ ] (선택) 1절의 `revoke ... from anon, authenticated` 실행
- [ ] (업로드 기능을 쓸 때만) **Storage** → New bucket `videos`, Public 켜기. 지금 서비스 흐름(YouTube·로컬 파일 분석)은 쓰지 않음

### 5-3. Auth

- [ ] **Authentication → Sign In / Providers → Email**: 켜기
- [ ] **Confirm email: 끄기 (현재 코드 기준 권장)**. 프론트엔드는 가입 후 「회원가입이 완료되었습니다. 로그인해주세요」만 보여 주고,
  백엔드 로그인은 이메일 확인 전이면 실패해 「이메일 또는 비밀번호가 올바르지 않습니다」로만 안내합니다. 켜려면 가입·로그인 화면에
  이메일 확인 안내를 먼저 추가해야 합니다.
- [ ] **Authentication → URL Configuration**
  - Site URL: 프론트엔드 주소. 개발 중이면 `http://localhost:3000`, 배포하면 그 주소
  - Redirect URLs: `http://localhost:3000/**`, `http://127.0.0.1:3000/**` (배포 주소가 있으면 추가)
  - 지금 코드는 이메일 링크(확인·비밀번호 재설정)를 쓰지 않아서, Confirm email을 끄면 이 값은 실제로 쓰이지 않습니다. 나중을 위해 맞춰 둡니다.
- [ ] 비밀번호 최소 길이 등은 기본값 그대로 둬도 됩니다(백엔드는 Supabase 오류 문구를 그대로 400으로 돌려줌).

### 5-4. 키 넣기

- [ ] **Project Settings → API**의 Project URL → `backend/.env.new`의 `SUPABASE_URL`
- [ ] **Project Settings → API Keys**의 service_role 키(secret) → `backend/.env.new`의 `SUPABASE_SERVICE_KEY`
  - 대시보드에 legacy `service_role` 키(JWT)와 새 형식 secret 키가 둘 다 보이면, 지금 팀 DB와 같은 형식인 service_role 키를 권장합니다.
    새 형식 키를 쓰면 4번 절의 확인(검색·회원가입·로그인)으로 백엔드(supabase-py 2.31.0)와 동작하는지 꼭 확인하세요.
- [ ] anon(publishable) 키는 필요 없습니다. 어디에도 넣지 않습니다.
- [ ] 키·URL은 `backend/.env*` 파일에만 두고 채팅·문서·커밋에 붙여넣지 않습니다.
