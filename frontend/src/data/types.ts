// 프론트와 백엔드가 주고받을 데이터 모양
// 백엔드 연동 시 이 타입에 맞춰 응답을 받으면 화면 코드를 거의 고치지 않아도 돼요.

/** 영상 장면 검증 상태 (VLM 재판별 결과) */
export type Verification = 'screen' | 'subtitle' | 'none';

/** 공식 정책정보 (사회보장 공공데이터 Open API) */
export interface Policy {
  policyId: string;
  name: string;
  category: string;
  target: string; // 받을 수 있는 분 (요약)
  incomeLimit: { single: string; couple: string };
  maxAmount: { single: number; couple: number };
  applyWhen: string;
  applyWhere: string;
  payDay: string;
  source: string;
  baseYear: number;
  updatedAt: string; // 최종 수정일
  applyUrl: string; // 공식 신청 페이지
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
  otherScenes?: { start: number; label: string }[];
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
