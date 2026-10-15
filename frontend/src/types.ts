export interface SearchResultItem
 {
  video_id: string;
  segment_id: string;
  start_time: number; // seconds (float)
  end_time: number;   // seconds (float)
  score: number;      // 0.0 - 1.0 (relevance score)
}

export interface SearchResponse {
  query: string;
  results: SearchResultItem[];
}

export interface Chapter {
  segment_id?: string;
  timestamp: number; // in seconds
  title: string;
}

export interface VideoMetadata {
  video_id: string;
  youtube_video_id?: string; // YouTube 영상 ID (11자리)

  title: string;
  category: string;
  categoryLabel: string;
  channelName: string;
  publishDate: string;
  views: string;
  thumbnailUrl: string;
  videoUrl: string;
  totalDuration: number; // in seconds
  chapters: Chapter[];
}

export interface SearchQueryExample {
  text: string;
  targetVideoId: string;
}

// 검색 결과 화면의 영상 카드 분석 상태
// checking: 첫 분석 상태 응답 전 (아직 모름), idle: 분석 전 (자동 분석 대상 아님, 클릭 시 분석),
// queued: 분석 대기, analyzing: 분석 중,
// done: 완료(구간 있음), no_results: 분석은 끝났지만 관련 구간 없음, failed: 분석 실패/불가
export type CardAnalysisStatus =
  | 'checking'
  | 'idle'
  | 'queued'
  | 'analyzing'
  | 'done'
  | 'no_results'
  | 'failed';

export interface CardStatusInfo {
  status: CardAnalysisStatus;
  // failed일 때 이유 (예: 30분 초과)
  reason?: string;
}

export interface SearchCard {
  youtubeVideoId: string;
  // YouTube 검색 결과 기준 메타데이터 (videosMap의 youtube_video_id 키)
  video: VideoMetadata;
  status: CardAnalysisStatus;
  reason?: string;
  // 관련도 높은 순으로 정렬된 AI 검색 구간 (done일 때만 채워짐)
  segments: SearchResultItem[];
  // YouTube 검색 순서 (0부터)
  youtubeRank: number;
}

// 분석 전 카드를 눌렀을 때 보여주는 분석 로딩 화면의 상태
export interface CardAnalysisState {
  card: SearchCard;
  // loading: 분석/검색 중, failed: 분석 실패, no_results: 관련 구간 없음
  phase: 'loading' | 'failed' | 'no_results';
  // 로딩 중 백엔드 분석 상태 (대기/분석 중 배지 표시용)
  status: 'queued' | 'analyzing';
  message?: string;
}
