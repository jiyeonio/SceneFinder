# SceneFinder 검색 API 명세 (v0.4)

## 공통 안내
- 개발 서버 주소: `http://127.0.0.1:8000` (서버를 켜면 `/docs`에서 직접 호출해 볼 수 있어요)
- **로그인**: 검색 관련 API(`/api/youtube/search`, `/api/search`, `/api/search/multi`, 상태 확인)는 로그인 없이 호출할 수 있어요. `Authorization: Bearer 토큰`을 같이 보내면 검색 기록이 저장돼요. 검색 기록 조회와 즐겨찾기 API는 로그인이 필수예요.
- **ID 구분**
  - 검색 API에 보내는 값은 `youtube_video_id`(유튜브 11자리 ID)예요.
  - 응답의 `video.video_id`는 DB 내부 uuid예요.
  - 즐겨찾기 API(`POST /api/users/me/favorites`)의 `video_id`는 내부 uuid이니, 검색 응답의 `video.video_id`를 그대로 넣어 주세요.
- **CORS**: 기본 허용 주소는 `localhost`/`127.0.0.1`의 3000, 5173 포트예요. 다른 주소가 필요하면 백엔드 `.env`의 `CORS_ORIGINS`에 추가해요.

## 흐름
1. 프론트가 `GET /api/youtube/search`로 영상 목록 조회
2. **영상 하나를 골라 검색**: 사용자가 영상 클릭 → `POST /api/search`
   - 이미 분석된 영상이면 바로 결과(200), 처음 보는 영상이면 분석 시작(202)
   - 202면 `GET .../status`를 2~3초마다 확인
   - `INDEXED`가 되면 `POST /api/search`를 다시 호출 → 결과(200)
3. **여러 영상을 한 번에 검색**: 화면의 영상 목록과 검색어로 `POST /api/search/multi` 호출
   - 분석된 영상은 구간 결과가 오고, 분석 안 된 영상은 `pending`에 담겨 와요.
   - `auto_analyze: true`로 보내면 분석 안 된 영상의 분석을 백그라운드로 시작해요. 이때 `pending`의 `status`가 `PROCESSING`으로 와요.
   - `pending` 영상은 `GET .../status`로 확인하거나, 사용자가 클릭할 때 2번 방식으로 분석을 시작할 수도 있어요.
4. 프론트가 `start_time`으로 유튜브 플레이어 seek

## 1. 유튜브 영상 검색
`GET /api/youtube/search?q=손흥민 골&max_results=10`
다음 페이지: `GET /api/youtube/search?q=손흥민 골&max_results=10&page_token=CAoQAA`

응답 200
```json
{
  "items": [
    {
      "youtube_video_id": "Ps8FeqKyFoM",
      "title": "영상 제목",
      "channel_name": "채널명",
      "thumbnail_url": "https://i.ytimg.com/vi/Ps8FeqKyFoM/mqdefault.jpg",
      "published_at": "2026-10-07T12:00:00Z"
    }
  ],
  "next_page_token": "CAoQAA"
}
```
- `max_results`는 1~50(기본 5)이에요.
- `next_page_token`이 있으면 다음 페이지가 있다는 뜻이고, 그 값을 `page_token`으로 보내면 이어서 가져와요. 없으면(`null`) 마지막 페이지예요.
- 같은 `q`로 이어서 불러야 해요. 토큰은 검색어마다 달라요.
- 유튜브 검색은 호출 한 번에 할당량 100이 들어서 하루 약 100회가 한계예요. 한 번에 `max_results`를 크게 받는 편이 호출 횟수를 줄여요.

## 2. 장면 검색 (영상 1개)
`POST /api/search`

요청
```json
{
  "youtube_video_id": "Ps8FeqKyFoM",
  "query": "골 넣고 세리머니하는 장면",
  "top_k": 5
}
```
`top_k`는 선택(기본 5, 최대 10)이고, URL은 백엔드가 만들어서 보내지 않아도 돼요.

응답 200 (분석 완료, 결과 있음)
```json
{
  "status": "INDEXED",
  "video": {
    "video_id": "내부 uuid",
    "youtube_video_id": "Ps8FeqKyFoM",
    "title": "영상 제목",
    "thumbnail_url": "https://..."
  },
  "query": "골 넣고 세리머니하는 장면",
  "results": [
    {
      "segment_id": "Ps8FeqKyFoM-1",
      "start_time": 132.4,
      "end_time": 145.0,
      "score": 0.87,
      "source": "visual"
    }
  ]
}
```
- `results`는 점수 높은 순이고, 시간은 초 단위(소수 가능)예요. 서로 많이 겹치는 구간은 하나만 남겨요.
- `source`는 결과를 찾은 방식이에요.
  - `subtitle`: 음성 자막(한국어)에서 찾았어요. 자막이 말한 시간 구간이에요.
  - `visual`: 영상 장면을 보고 찾았어요.
  - `source`에 따라 `score`의 의미가 달라요. 자막 점수는 문장 유사도(0~1)이고, 영상 점수는 모델 출력값이에요. **서로 직접 비교하지 마세요.**
- 한국어 자막이 있고 유사도가 충분하면 `subtitle` 결과가 오고, 자막이 없거나 유사도가 낮으면 `visual` 결과로 대체돼요.

응답 202 (처음 보는 영상, 분석 시작됨)
```json
{
  "status": "PROCESSING",
  "youtube_video_id": "Ps8FeqKyFoM",
  "message": "영상을 분석 중입니다."
}
```
분석에는 영상 길이에 따라 수십 초~몇 분이 걸려요. 분석이 끝난 영상의 검색 자체는 1초 안팎이에요. 분석에는 영상 다운로드, 특징 추출, 음성 자막 생성이 포함돼요.

## 3. 분석 상태 확인
`GET /api/videos/youtube/{youtube_video_id}/status`

```json
{
  "youtube_video_id": "Ps8FeqKyFoM",
  "status": "PROCESSING",
  "error_message": null
}
```
`status`는 `PENDING` / `PROCESSING` / `INDEXED` / `FAILED` 중 하나예요. 다운로드나 분석이 실패하면 `FAILED`가 되고 `error_message`에 사유가 들어가요. 등록되지 않은 영상이면 404(`VIDEO_NOT_FOUND`)예요. `FAILED` 영상은 `POST /api/search`로 다시 시도할 수 있어요.

## 4. 다중 장면 검색
`POST /api/search/multi`

요청
```json
{
  "query": "골 세리머니",
  "youtube_video_ids": ["Ps8FeqKyFoM", "a6Nw3y07Zs8"],
  "top_k_per_video": 3,
  "max_videos": 10,
  "auto_analyze": true,
  "max_new_analyses": 3
}
```
- `youtube_video_ids`는 선택이에요. 생략하면 분석 완료된 영상 전체가 대상이에요. (최대 30개)
- `top_k_per_video`는 1~5(기본 3), `max_videos`는 1~30(기본 10)이에요.
- `auto_analyze`는 선택(기본 `false`)이에요. `true`면 `youtube_video_ids`에 있는 미분석 영상의 분석을 시작해요.
- `max_new_analyses`는 한 번의 요청으로 새로 시작할 최대 영상 수예요(기본 3, 최대 5).
- 분석을 새로 시작하는 건 `NOT_ANALYZED`/`PENDING` 상태 영상뿐이에요. `FAILED`는 자동 재시도하지 않아요.

응답 200
```json
{
  "query": "골 세리머니",
  "videos": [
    {
      "video": {
        "video_id": "내부 uuid",
        "youtube_video_id": "Ps8FeqKyFoM",
        "title": "영상 제목",
        "channel_name": "채널명",
        "thumbnail_url": "https://..."
      },
      "best_score": 0.9,
      "moments": [
        { "segment_id": "Ps8FeqKyFoM-1", "start_time": 132.4, "end_time": 145.0, "score": 0.9, "source": "visual" }
      ]
    }
  ],
  "pending": [
    { "youtube_video_id": "a6Nw3y07Zs8", "status": "PROCESSING" }
  ]
}
```
- `videos`는 `best_score` 높은 순이고, 분석이 끝난(`INDEXED`) 영상만 들어가요. `best_score`는 `source`에 따라 의미가 달라서 영상 간 순서는 참고용이에요.
- `pending`은 아직 결과가 없는 영상이에요. `status`는 아래 중 하나예요.

| status | 의미 |
|---|---|
| NOT_ANALYZED | 아직 분석을 시작하지 않음 (`auto_analyze: false`이거나 한도를 넘음) |
| PENDING | 등록은 됐지만 분석 대기 중 |
| PROCESSING | 분석 중 (프론트가 `GET .../status`로 확인) |
| FAILED | 분석 실패 (사용자가 클릭하면 `POST /api/search`로 재시도) |
| TOO_LONG | 길이 제한(현재 30분) 초과로 분석 불가 |
| NOT_FOUND | 유튜브에서 영상을 찾을 수 없음 |

- 시간은 모두 초 단위(소수 가능)예요.

## 5. 회원가입 / 로그인
`POST /api/auth/signup`
```json
{ "email": "user@example.com", "password": "비밀번호", "name": "홍길동" }
```
`name`은 선택이에요(표시 이름). 안 보내면 `null`로 와요.

응답 200
```json
{ "user_id": "uuid", "email": "user@example.com", "name": "홍길동" }
```

`POST /api/auth/login` (같은 요청 형식)

응답 200
```json
{
  "access_token": "...",
  "refresh_token": "...",
  "user_id": "uuid",
  "email": "user@example.com",
  "name": "홍길동"
}
```
- 로그인 실패는 401이에요.
- 이후 요청에는 `Authorization: Bearer {access_token}` 헤더를 보내요. 토큰은 약 1시간 후 만료돼요.
- 이메일 인증 없이 가입 직후 로그인할 수 있어요.

## 6. 검색 기록 / 즐겨찾기 (로그인 필수)
- `GET /api/users/me/history` → `{ "history": [ { "query": "...", "searched_at": "..." } ] }` (최신순)
- `POST /api/users/me/favorites`
  ```json
  { "youtube_video_id": "Ps8FeqKyFoM", "start_time": 132.4, "end_time": 145.0 }
  ```
  - 영상은 `youtube_video_id` 또는 `video_id`(내부 uuid) 중 하나로 지정해요. 등록되지 않은 영상이면 404예요.
  - 응답: 저장된 즐겨찾기(`favorite_id` 포함)와 영상 정보
  ```json
  {
    "favorite_id": "uuid", "user_id": "uuid", "video_id": "내부 uuid",
    "start_time": 132.4, "end_time": 145.0, "created_at": "2026-10-12T07:39:48+00:00",
    "video": {
      "video_id": "내부 uuid", "youtube_video_id": "Ps8FeqKyFoM",
      "title": "영상 제목", "channel_name": "채널명", "thumbnail_url": "https://..."
    }
  }
  ```
- `GET /api/users/me/favorites` → `{ "favorites": [ ... ] }` (최신순, 각 항목에 위와 같은 `video` 포함)
- `DELETE /api/users/me/favorites/{favorite_id}` → `{ "status": "deleted" }`

## 7. 에러 응답 (공통)
```json
{ "error": { "code": "INVALID_YOUTUBE_ID", "message": "올바르지 않은 영상 ID입니다." } }
```

| HTTP | code | 의미 |
|---|---|---|
| 400 | INVALID_YOUTUBE_ID | 영상 ID 형식 오류 |
| 400 | EMPTY_QUERY | 검색어가 비어 있음 |
| 404 | VIDEO_NOT_FOUND | 유튜브에 없는 영상이거나 등록되지 않은 영상 |
| 422 | VIDEO_TOO_LONG | 길이 제한(현재 30분) 초과 |
| 502 | YOUTUBE_ERROR | 유튜브 API 호출 실패 |
| 503 | YOUTUBE_QUOTA | 유튜브 API 일일 한도 초과 |

인증 관련 에러(로그인 실패, 토큰 오류)는 FastAPI 기본 형식 `{ "detail": "..." }`로 와요.

## 현재 정해진 것과 확인 중인 것
- 로그인: 검색은 로그인 없이 가능, 검색 기록과 즐겨찾기는 필수 (정해짐)
- 분석 가능한 영상 최대 길이: 현재 **30분** (임시값, 팀 논의 후 조정)
- 한국어 검색: 한국어 자막이 있으면 자막 검색(MiniLM), 없거나 유사도가 낮으면 영상 검색(Moment-DETR)으로 대체 (구현됨)
- `score` 해석: `source`별로 다르며 서로 비교하지 않음. 영상 간 정렬 기준은 AI 파트에 확인 중
- 자막 유사도 최소값: 기본 0.35 (임시값, 실제 영상으로 조정 예정)