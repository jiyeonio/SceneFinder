// 데이터 불러오기 — VITE_API_BASE_URL 이 있으면 복지바로봄 백엔드, 없으면 가짜 데이터
import { basicPension, sceneResults, videoDetail } from './mock';
import type { OfficialAnswer, Policy, SceneResult, VideoDetail } from './types';

const BASE = import.meta.env.VITE_API_BASE_URL as string | undefined;

export interface SearchResponse {
  query: string;
  policies: Policy[];
  scenes: SceneResult[];
  /** VLM 화면 확인 작업 id — status가 'pending'이면 pollSearch로 갱신 */
  jobId?: string;
  status?: 'pending' | 'done' | 'error';
  official?: OfficialAnswer | null;
  /** 영상에 답이 없을 때 안내 (예: 신청 기간 질문) */
  notice?: { show: boolean; reason: string | null; message: string };
}

export async function searchWelfare(query: string, policy?: string): Promise<SearchResponse> {
  if (BASE) {
    const p = policy ? `&policy=${encodeURIComponent(policy)}` : '';
    const res = await fetch(`${BASE}/api/welfare/search?q=${encodeURIComponent(query)}${p}`);
    if (!res.ok) throw new Error('검색에 실패했어요');
    return res.json();
  }
  return { query, policies: [basicPension], scenes: sceneResults, status: 'done' };
}

/** VLM 화면 확인이 끝날 때까지 갱신된 결과를 받음 */
export async function pollSearch(jobId: string): Promise<SearchResponse> {
  const res = await fetch(`${BASE}/api/welfare/search/${jobId}`);
  if (!res.ok) throw new Error('검색 결과를 갱신하지 못했어요');
  return res.json();
}

export async function getVideo(videoId: string, opts: { jobId?: string; t?: number } = {}): Promise<VideoDetail> {
  if (BASE) {
    const q = new URLSearchParams();
    if (opts.jobId) q.set('jobId', opts.jobId);
    if (opts.t !== undefined) q.set('t', String(opts.t));
    const res = await fetch(`${BASE}/api/videos/${videoId}?${q}`);
    if (!res.ok) throw new Error('영상 정보를 불러오지 못했어요');
    return res.json();
  }
  return videoDetail;
}
