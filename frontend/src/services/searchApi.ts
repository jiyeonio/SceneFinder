
import { SearchResponse, SearchResultItem, VideoMetadata } from '../types';
import { DEFAULT_SEARCH_RESPONSES } from '../data/mockData';

/**
 * 기존 Mock 검색 함수
 * 기존 화면과의 호환성을 위해 유지합니다.
 */
export async function searchVideoSegments(
  query: string
): Promise<SearchResponse> {
  const trimmed = query.trim();

  await new Promise((resolve) => setTimeout(resolve, 350));

  if (!trimmed) {
    return {
      query: '',
      results: [],
    };
  }

  if (DEFAULT_SEARCH_RESPONSES[trimmed]) {
    const resp = DEFAULT_SEARCH_RESPONSES[trimmed];

    return {
      query: trimmed,
      results: [...resp.results].sort((a, b) => b.score - a.score),
    };
  }

  for (const [knownQuery, resp] of Object.entries(DEFAULT_SEARCH_RESPONSES)) {
    if (
      trimmed.includes('배터리') ||
      trimmed.includes('에어팟') ||
      trimmed.includes('이어폰')
    ) {
      if (knownQuery.includes('배터리')) {
        return {
          query: trimmed,
          results: [...resp.results].sort((a, b) => b.score - a.score),
        };
      }
    }

    if (
      trimmed.includes('실험') ||
      trimmed.includes('피펫') ||
      trimmed.includes('용액')
    ) {
      if (knownQuery.includes('용액')) {
        return {
          query: trimmed,
          results: [...resp.results].sort((a, b) => b.score - a.score),
        };
      }
    }

    if (
      trimmed.includes('골') ||
      trimmed.includes('축구') ||
      trimmed.includes('경기') ||
      trimmed.includes('세레머니')
    ) {
      if (knownQuery.includes('골')) {
        return {
          query: trimmed,
          results: [...resp.results].sort((a, b) => b.score - a.score),
        };
      }
    }

    if (
      trimmed.includes('문') ||
      trimmed.includes('인테리어') ||
      trimmed.includes('투어') ||
      trimmed.includes('방')
    ) {
      if (knownQuery.includes('문')) {
        return {
          query: trimmed,
          results: [...resp.results].sort((a, b) => b.score - a.score),
        };
      }
    }
  }

  if (
    trimmed.includes('없는') ||
    trimmed.includes('null') ||
    trimmed.includes('empty')
  ) {
    return {
      query: trimmed,
      results: [],
    };
  }

  const dynamicResults: SearchResultItem[] = [
    {
      video_id: 'abc123',
      segment_id: 'abc123_seg_021',
      start_time: 203.4,
      end_time: 241.7,
      score: 0.93,
    },
    {
      video_id: 'xyz789',
      segment_id: 'xyz789_seg_008',
      start_time: 78.2,
      end_time: 109.4,
      score: 0.88,
    },
    {
      video_id: 'vlog456',
      segment_id: 'vlog456_seg_014',
      start_time: 132.0,
      end_time: 170.0,
      score: 0.84,
    },
    {
      video_id: 'sport101',
      segment_id: 'sport101_seg_033',
      start_time: 165.0,
      end_time: 210.0,
      score: 0.79,
    },
  ];

  return {
    query: trimmed,
    results: dynamicResults.sort((a, b) => b.score - a.score),
  };
}

// ===================== 공통 API 설정 =====================

// 백엔드 주소는 frontend/.env의 VITE_API_BASE_URL로 바꿀 수 있습니다.
export const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'
).replace(/\/+$/, '');

function getAuthHeaders(): Record<string, string> {
  const token = localStorage.getItem('scenefinder-access-token');

  return {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

// ===================== YouTube 영상 검색 =====================

export interface YouTubeVideoItem {
  youtube_video_id: string;
  title: string;
  channel_name: string;
  thumbnail_url: string;
  published_at: string;
  // 영상 길이(초). 조회 실패 시 null
  duration?: number | null;
}

export interface YouTubeSearchResponse {
  items: YouTubeVideoItem[];
}

export async function searchYouTubeVideos(
  query: string,
  maxResults = 5
): Promise<YouTubeSearchResponse> {
  const params = new URLSearchParams({
    q: query.trim(),
    max_results: String(maxResults),
  });

  const response = await fetch(
    `${API_BASE_URL}/api/youtube/search?${params.toString()}`
  );

  if (!response.ok) {
    throw new Error(
      `YouTube 영상 검색 실패 (HTTP ${response.status})`
    );
  }

  return (await response.json()) as YouTubeSearchResponse;
}

// ===================== 다중 영상 AI 검색 =====================

export type MomentSource = 'subtitle' | 'visual';

export interface MomentResult {
  segment_id: string;
  start_time: number;
  end_time: number;

  // 자막 검색 결과에서는 null일 수 있습니다.
  score: number | null;

  // 최신 AI 모델에서 추가된 응답 필드입니다.
  source?: MomentSource;
  subtitle_score?: number | null;
}

export interface MultiSearchVideo {
  video: {
    video_id: string;
    youtube_video_id: string;
    title: string;
    channel_name: string;
    thumbnail_url: string;
  };
  best_score: number | null;
  moments: MomentResult[];
}

export type PendingVideoStatus =
  | 'NOT_ANALYZED'
  | 'PENDING'
  | 'PROCESSING'
  | 'FAILED'
  | 'TOO_LONG'
  | 'NOT_FOUND';

export interface PendingVideo {
  youtube_video_id: string;
  status: PendingVideoStatus;
}

export interface MultiSearchResponse {
  query: string;
  videos: MultiSearchVideo[];
  pending: PendingVideo[];
}

/**
 * 여러 영상의 AI 검색 결과를 가져옵니다.
 *
 * autoAnalyze=true:
 * 미분석 영상의 분석을 백그라운드에서 자동 시작합니다.
 *
 * 분석 중인 영상이 있으면 App.tsx에서
 * 동일한 검색 요청을 3초 간격으로 다시 호출합니다.
 */
// 검색 1번당 자동으로 분석을 시작할 영상 수 (나머지는 카드 클릭 시 분석)
// YouTube 다운로드 제한을 피하려고 줄여 둠. 백엔드도 요청 1번당 최대 5개로 제한합니다.
export const AUTO_ANALYZE_COUNT = Math.min(
  5,
  Math.max(0, Number(import.meta.env.VITE_AUTO_ANALYZE_COUNT ?? 5) || 0)
);

export async function searchMultipleVideos(
  query: string,
  youtubeVideoIds: string[],
  topKPerVideo = 3,
  autoAnalyze = true,
  maxNewAnalyses = AUTO_ANALYZE_COUNT
): Promise<MultiSearchResponse> {
  const response = await fetch(`${API_BASE_URL}/api/search/multi`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify({
      query: query.trim(),
      youtube_video_ids: youtubeVideoIds,
      top_k_per_video: topKPerVideo,
      max_videos: 20,
      auto_analyze: autoAnalyze && maxNewAnalyses > 0,
      max_new_analyses: maxNewAnalyses,
    }),
  });

  if (!response.ok) {
    throw new Error(
      `다중 영상 검색 실패 (HTTP ${response.status})`
    );
  }

  return (await response.json()) as MultiSearchResponse;
}

// ===================== 영상 분석 상태 확인 =====================

export type VideoAnalysisStatus =
  | 'NOT_ANALYZED'
  | 'PENDING'
  | 'PROCESSING'
  | 'INDEXED'
  | 'FAILED'
  | 'TOO_LONG'
  | 'NOT_FOUND';

export interface VideoStatusResponse {
  youtube_video_id: string;
  status: VideoAnalysisStatus;
  error_message: string | null;
}

export async function getYouTubeVideoStatus(
  youtubeVideoId: string
): Promise<VideoStatusResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api/videos/youtube/${encodeURIComponent(
      youtubeVideoId
    )}/status`
  );

  if (!response.ok) {
    throw new Error(
      `영상 분석 상태 확인 실패 (HTTP ${response.status})`
    );
  }

  return (await response.json()) as VideoStatusResponse;
}

// ===================== 개별 영상 분석 / 검색 =====================

export interface SingleSearchResponse {
  status?: 'INDEXED' | 'PROCESSING';
  youtube_video_id?: string;
  message?: string;
  query?: string;
  video?: {
    video_id: string;
    youtube_video_id: string;
    title: string;
    thumbnail_url: string;
  };
  results?: MomentResult[];
}

export async function searchSingleVideo(
  youtubeVideoId: string,
  query: string,
  topK = 5
): Promise<SingleSearchResponse> {
  const response = await fetch(`${API_BASE_URL}/api/search`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify({
      youtube_video_id: youtubeVideoId,
      query: query.trim(),
      top_k: topK,
    }),
  });

  if (!response.ok && response.status !== 202) {
    // 백엔드 오류 메시지(예: 30분 이하 영상만 분석 가능)를 그대로 전달
    const body = await response.json().catch(() => null);
    throw new Error(
      body?.error?.message ??
        `개별 영상 검색 실패 (HTTP ${response.status})`
    );
  }

  return (await response.json()) as SingleSearchResponse;
}

// ===================== 백엔드 결과 → 프론트 데이터 =====================

/**
 * 실제 점수가 없는 경우 임의의 점수를 만들지 않습니다.
 * 검색 결과 화면의 score는 숫자여야 하므로,
 * 점수가 없는 항목은 결과 목록에서 제외합니다.
 */
function getMomentScore(moment: MomentResult): number | null {
  const candidates =
    moment.source === 'subtitle'
      ? [moment.subtitle_score, moment.score]
      : [moment.score, moment.subtitle_score];

  for (const candidate of candidates) {
    if (
      typeof candidate === 'number' &&
      Number.isFinite(candidate)
    ) {
      return candidate;
    }
  }

  return null;
}

export function convertMultiSearchResults(
  response: MultiSearchResponse
): {
  results: SearchResultItem[];
  videos: Record<string, VideoMetadata>;
} {
  const results: SearchResultItem[] = [];
  const videos: Record<string, VideoMetadata> = {};

  for (const entry of response.videos ?? []) {
    const video = entry.video;

    videos[video.video_id] = {
      video_id: video.video_id,
      youtube_video_id: video.youtube_video_id,
      title: video.title,
      category: 'youtube',
      categoryLabel: 'YouTube',
      channelName: video.channel_name,
      publishDate: '',
      views: '',
      thumbnailUrl: video.thumbnail_url,
      videoUrl: `https://www.youtube.com/watch?v=${video.youtube_video_id}`,
      totalDuration: 0,
      chapters: [],
    };

    for (const moment of entry.moments ?? []) {
      const score = getMomentScore(moment);

      if (score === null) {
        console.warn(
          '유효한 점수가 없어 검색 결과에서 제외했습니다:',
          moment
        );
        continue;
      }

      results.push({
        video_id: video.video_id,
        segment_id: moment.segment_id,
        start_time: moment.start_time,
        end_time: moment.end_time,
        score,
      });
    }
  }

  results.sort((a, b) => b.score - a.score);

  return { results, videos };
}

/**
 * 개별 영상 검색(POST /api/search) 결과를 화면용 데이터로 바꿉니다.
 * youtubeVideo: YouTube 검색에서 받은 메타데이터 (채널, 길이 등을 채우기 위해 사용)
 */
export function convertSingleSearchResults(
  response: SingleSearchResponse,
  youtubeVideo?: VideoMetadata
): {
  results: SearchResultItem[];
  video: VideoMetadata | null;
} {
  const v = response.video;

  if (!v) {
    return { results: [], video: null };
  }

  const video: VideoMetadata = {
    video_id: v.video_id,
    youtube_video_id: v.youtube_video_id,
    title: v.title,
    category: 'youtube',
    categoryLabel: 'YouTube',
    channelName: youtubeVideo?.channelName ?? '',
    publishDate: youtubeVideo?.publishDate ?? '',
    views: '',
    thumbnailUrl: v.thumbnail_url,
    videoUrl: `https://www.youtube.com/watch?v=${v.youtube_video_id}`,
    totalDuration: youtubeVideo?.totalDuration ?? 0,
    chapters: [],
  };

  const results: SearchResultItem[] = [];

  for (const moment of response.results ?? []) {
    const score = getMomentScore(moment);
    if (score === null) continue;

    results.push({
      video_id: v.video_id,
      segment_id: moment.segment_id,
      start_time: moment.start_time,
      end_time: moment.end_time,
      score,
    });
  }

  results.sort((a, b) => b.score - a.score);

  return { results, video };
}
