// 프론트와 백엔드가 주고받을 데이터 모양
// 백엔드 연동 시 이 타입에 맞춰 응답을 받으면 화면 코드를 거의 고치지 않아도 돼요.

/** 영상 장면 검증 상태 (VLM 재판별 결과). pending = AI가 화면을 확인하는 중 (확인 뒤 갱신) */
export type Verification = 'screen' | 'subtitle' | 'none' | 'pending';

/** 공식 정책정보 (사회보장 공공데이터 Open API: 한국사회보장정보원 복지서비스정보 · 행정안전부 공공서비스(혜택)) */
export interface Policy {
  policyId: string;
  name: string;
  category: string;
  target: string; // 한 줄 요약
  targetDetail: string; // 지원대상
  criteria: string; // 선정기준
  benefit: string; // 지원내용
  applyMethod: string; // 신청방법
  applyWhen: string; // 신청기한
  requiredDocs: string[]; // 구비서류
  contact: string; // 문의처
  agency: string; // 소관기관
  applyUrl: string; // 공식 신청 페이지
  officialUrls: { label: string; url: string }[];
  /** 금액 정보가 있는 정책만 (예: 기초연금). 공식 지원내용 원문에 있는 문구 그대로 */
  amount: { label: string; value: string }[] | null;
  source: string;
  baseYear: number | null;
  updatedAt: string; // 최종 수정일
  fetchedAt?: string; // 공공데이터를 받은 날
}

/** 공식 정보로 답한 항목 (질문 의도에 맞는 정책 항목) */
export interface OfficialAnswer {
  policyId: string;
  items: { intent: string; field: string; value: unknown }[];
  source: string;
  baseYear: number | null;
  updatedAt: string;
}

/** 검색 결과의 영상 1개 + AI가 찾은 장면 */
export interface SceneResult {
  videoId: string;
  youtubeVideoId?: string;
  title: string;
  publisher: string;
  publishedAt: string;
  duration: string;
  thumbType?: 'screen' | 'paper' | 'phone'; // 실제 썸네일이 오기 전까지 쓰는 모양
  thumbnailUrl?: string;
  found: {
    start: number; // 초
    end: number;
    label: string;
    verification: Verification;
  };
  otherScenes?: { start: number; end?: number; label: string; verification?: Verification }[];
}

/** 영상 상세의 장면(챕터) — Policy-to-Scene Grounding 결과 */
export interface Chapter {
  id: string;
  start: number;
  end: number;
  title: string;
  short: string; // 타임라인에 쓰는 짧은 이름
  step: number | null; // 신청 단계 (없으면 null)
  stepLabel: string;
  verification: Verification;
  subtitle: string; // 대표 자막
  screenTitle: string; // 화면 예시 제목
  relatedDocs: string[]; // 이 장면에서 쓰는 서류 id
  follow?: { title: string; desc: string; at: number }[]; // 이 장면 따라 하기
  gap?: boolean; // 장면 사이 빈 곳 (타임라인·목록에는 안 보임)
}

export interface VideoDetail {
  videoId: string;
  youtubeVideoId?: string;
  title: string;
  publisher: string;
  publishedAt: string;
  durationSec: number;
  query: string;
  matchedChapterId: string;
  chapters: Chapter[];
  policy: Policy | null;
  docs: DocItem[];
  officialSteps: OfficialStep[];
  subtitles?: { start: number; end: number; text: string }[]; // 큰 자막용
  stepsStatus?: 'draft' | 'reviewed' | null; // 단계 카드 검수 상태
}

export interface DocItem {
  id: string;
  name: string;
  note?: string;
}

export interface OfficialStep {
  step: number;
  title: string;
  note: string;
  videoAt?: number; // 영상 속 시작 시간 (없으면 '해당 장면 없음')
  verification: Verification;
}
