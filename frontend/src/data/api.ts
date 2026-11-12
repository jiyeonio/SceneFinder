// 데이터 불러오기 — 지금은 가짜 데이터, 나중에 백엔드 API로 교체
// .env 에 VITE_API_BASE_URL 을 넣으면 실제 API를 부르도록 바꾸면 돼요.
import { basicPension, sceneResults, videoDetail } from './mock';
import type { Policy, SceneResult, VideoDetail } from './types';

const BASE = import.meta.env.VITE_API_BASE_URL as string | undefined;

export interface SearchResponse {
  query: string;
  policies: Policy[];
  scenes: SceneResult[];
}

export async function searchWelfare(query: string): Promise<SearchResponse> {
  if (BASE) {
    // 예: GET /api/welfare/search?q=...
    const res = await fetch(`${BASE}/api/welfare/search?q=${encodeURIComponent(query)}`);
    if (!res.ok) throw new Error('검색에 실패했어요');
    return res.json();
  }
  return { query, policies: [basicPension], scenes: sceneResults };
}

export async function getVideo(videoId: string): Promise<VideoDetail> {
  if (BASE) {
    const res = await fetch(`${BASE}/api/videos/${videoId}`);
    if (!res.ok) throw new Error('영상 정보를 불러오지 못했어요');
    return res.json();
  }
  return videoDetail;
}
