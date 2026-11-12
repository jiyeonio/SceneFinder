# 복지바로봄 웹 (프론트엔드 시제품)

파란색 2안 디자인을 React + Vite + TypeScript로 옮긴 프로젝트예요.
지금은 **가짜 데이터(mock)** 로 동작해서 백엔드 없이도 모든 화면을 눌러볼 수 있어요.

## 1. 실행 방법

1. **Node.js 설치** (처음 한 번만) — https://nodejs.org 에서 LTS 버전 설치
2. zip을 풀고 VS Code에서 `파일 → 폴더 열기`로 이 폴더(`bokjibarobom-web`)를 열기
3. VS Code 메뉴 `터미널 → 새 터미널`을 열고 아래 두 줄 입력

```bash
npm install      # 처음 한 번만 (필요한 패키지 설치)
npm run dev      # 개발 서버 실행
```

4. 브라우저가 자동으로 열려요. 안 열리면 터미널에 나온 주소 `http://localhost:5173` 을 직접 열기
5. 코드를 고치고 저장하면 브라우저 화면이 바로 바뀌어요. 끌 때는 터미널에서 `Ctrl + C`

## 2. 화면 주소

| 화면 | 주소 |
|---|---|
| 홈 | `http://localhost:5173/#/` |
| 검색 결과 | `http://localhost:5173/#/results?q=기초연금` |
| 영상 상세 | `http://localhost:5173/#/watch/v1` (`?t=515` 를 붙이면 그 시간부터) |
| 이용 안내 | `http://localhost:5173/#/guide` |

## 3. 폴더 구조

```
src/
├─ main.tsx              # 시작점
├─ App.tsx               # 주소에 따라 화면 바꾸기
├─ router.ts             # 간단한 주소(#/...) 처리
├─ utils.ts              # 시간·금액 표시 도우미
├─ components/
│  ├─ Layout.tsx         # 접근성 바(글자 크기·고대비) + 헤더 + 푸터
│  ├─ Icon.tsx           # 아이콘
│  └─ Common.tsx         # 썸네일, 검증 배지, 출처 라벨, 장면 행
├─ pages/
│  ├─ Home.tsx           # 홈
│  ├─ Results.tsx        # 검색 결과
│  ├─ Watch.tsx          # 영상 상세 (가장 중요)
│  └─ Guide.tsx          # 이용 안내
├─ data/
│  ├─ types.ts           # ★ 백엔드와 주고받을 데이터 모양
│  ├─ mock.ts            # 시연용 가짜 데이터
│  └─ api.ts             # ★ 데이터 불러오기 (여기서 백엔드 연결)
└─ styles/               # base.css(공통) + 화면별 CSS
```

## 4. 백엔드·AI 연동 방법

1. 백엔드 친구와 `src/data/types.ts` 의 데이터 모양을 먼저 맞춰요.
   - 영상 장면: `start`, `end`(초), `step`(신청 단계), `verification`(`screen` 실제 화면 / `subtitle` 자막만 / `none` 해당 장면 없음)
2. `.env.example` 을 복사해 `.env` 를 만들고 백엔드 주소를 적어요.
   ```
   VITE_API_BASE_URL=http://127.0.0.1:8000
   ```
3. `src/data/api.ts` 의 `searchWelfare`, `getVideo` 가 그 주소의 API를 부르도록 되어 있어요. 주소 이름이 다르면 여기만 고치면 돼요.
4. 영상 플레이어: `src/pages/Watch.tsx` 의 `.stage` 부분이 지금은 화면 모양만 그린 자리예요. 실제 영상(YouTube 등)으로 바꾸고, 플레이어의 현재 시간을 `time` 상태에 연결하면 장면 강조·따라 하기·정책 패널이 자동으로 따라 움직여요.

## 5. 참고

- 화면의 금액·날짜·영상 시간은 시연용 예시예요. `[게시기관]`, `[YYYY.MM.DD]` 는 실제 값으로 채워 주세요.
- 글자 크기·고대비 설정은 브라우저에 저장돼서 다시 열어도 유지돼요.
- `npm run build` 로 배포용 파일(`dist/`)을 만들 수 있어요. `npm run typecheck` 로 타입 검사를 할 수 있어요.
