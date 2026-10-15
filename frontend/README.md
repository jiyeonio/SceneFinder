# SceneFinder Frontend

React + Vite 웹 UI입니다. 전체 실행 방법과 환경변수 설명은 [루트 README의 실행 방법](../README.md#실행-방법)을 참고하세요.

## 실행

**준비물:** Node.js 20 이상, 실행 중인 백엔드(기본 `http://127.0.0.1:8000`)

1. 패키지 설치: `npm install`
2. 환경변수 파일 만들기: `cp .env.example .env`
   - `VITE_API_BASE_URL`: 백엔드 주소
   - `VITE_AUTO_ANALYZE_COUNT`: 검색 1번당 자동 분석할 영상 수 (0~5, 기본 5). 나머지는 카드를 눌렀을 때만 분석합니다.
   - `VITE_` 값은 브라우저에 노출되므로 비밀값을 넣지 마세요.
3. 개발 서버 실행: `npm run dev` → http://localhost:3000

타입 검사는 `npm run lint`, 배포용 빌드는 `npm run build`입니다.
