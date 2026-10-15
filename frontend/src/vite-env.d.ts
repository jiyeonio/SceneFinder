/// <reference types="vite/client" />

interface ImportMetaEnv {
  // 백엔드 API 주소 (예: http://127.0.0.1:8000). 비우면 이 기본값을 사용합니다.
  readonly VITE_API_BASE_URL?: string;
  // 검색 1번당 자동 분석할 영상 수 (0~5, 기본 5). 나머지는 카드 클릭 시 분석
  readonly VITE_AUTO_ANALYZE_COUNT?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
