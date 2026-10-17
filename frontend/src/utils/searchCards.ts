import {
  CardStatusInfo,
  SearchCard,
  SearchResultItem,
  VideoMetadata,
} from '../types';
import { byBackendRank, MultiSearchResponse } from '../services/searchApi';

/**
 * /api/search/multi 응답으로 영상별 분석 상태를 계산합니다.
 *
 * - videos에 있으면: 완료 (구간 있음)
 * - pending에 있으면: 백엔드 상태에 따라 대기/분석 중/실패
 * - 둘 다 없으면: 분석은 끝났지만 관련 구간이 없음
 */
export function deriveCardStatuses(
  youtubeVideoIds: string[],
  response: MultiSearchResponse
): Record<string, CardStatusInfo> {
  const done = new Set(
    (response.videos ?? []).map((entry) => entry.video.youtube_video_id)
  );
  const captionStatuses = new Map(
    (response.videos ?? []).map((entry) => [entry.video.youtube_video_id, entry.caption_status])
  );
  const pending = new Map(
    (response.pending ?? []).map((item) => [item.youtube_video_id, item.status])
  );

  const statuses: Record<string, CardStatusInfo> = {};

  for (const id of youtubeVideoIds) {
    if (done.has(id)) {
      statuses[id] = { status: 'done', captionStatus: captionStatuses.get(id) };
      continue;
    }

    switch (pending.get(id)) {
      case undefined:
        statuses[id] = { status: 'no_results' };
        break;
      // 자동 분석 대상이 아니어서 아직 시작하지 않은 영상: 카드를 누르면 분석
      case 'NOT_ANALYZED':
      case 'PENDING':
        statuses[id] = { status: 'idle' };
        break;
      case 'PROCESSING':
        statuses[id] = { status: 'analyzing' };
        break;
      case 'TOO_LONG':
        statuses[id] = { status: 'failed', reason: '30분 초과 영상' };
        break;
      case 'NOT_FOUND':
        statuses[id] = { status: 'failed', reason: '영상을 찾을 수 없음' };
        break;
      default:
        statuses[id] = { status: 'failed' };
    }
  }

  return statuses;
}

/**
 * 화면에 표시할 카드 목록을 만듭니다.
 *
 * 순서는 항상 YouTube 검색 순서로 고정합니다.
 * 분석이 끝나도 재정렬하지 않고 카드 내용(상태, AI 구간 정보)만 바뀝니다.
 */
export function buildSearchCards(
  youtubeVideoIds: string[],
  statuses: Record<string, CardStatusInfo>,
  results: SearchResultItem[],
  videosMap: Record<string, VideoMetadata>
): SearchCard[] {
  // 결과의 video_id(DB uuid) → YouTube ID로 묶기
  const segmentsByYid = new Map<string, SearchResultItem[]>();

  for (const item of results) {
    const yid = videosMap[item.video_id]?.youtube_video_id;
    if (!yid) continue;

    const list = segmentsByYid.get(yid) ?? [];
    list.push(item);
    segmentsByYid.set(yid, list);
  }

  const cards: SearchCard[] = [];

  youtubeVideoIds.forEach((yid, youtubeRank) => {
    const video = videosMap[yid];
    if (!video) return;

    const info = statuses[yid] ?? { status: 'queued' };
    // 백엔드가 정한 순서 (자막·화면 설명이 섞이면 점수 척도가 달라 점수로 다시 정렬하지 않음)
    const segments = [...(segmentsByYid.get(yid) ?? [])].sort(byBackendRank);

    // 점수가 있는 구간이 하나도 없으면 '결과 없음'으로 표시
    const status =
      info.status === 'done' && segments.length === 0
        ? 'no_results'
        : info.status;

    cards.push({
      youtubeVideoId: yid,
      video,
      status,
      reason: info.reason,
      captionStatus: info.captionStatus,
      segments,
      youtubeRank,
    });
  });

  return cards;
}

/** 아직 분석이 끝나지 않은 카드가 있는지 (polling 계속 여부) */
export function hasUnfinishedCards(
  statuses: Record<string, CardStatusInfo>
): boolean {
  return Object.values(statuses).some(
    (info) =>
      info.status === 'checking' ||
      info.status === 'queued' ||
      info.status === 'analyzing'
  );
}

/** 화면 설명(설명문)을 만드는 중인 영상이 있는지 (끝나면 결과가 바뀌므로 갱신 계속) */
export function hasCaptionsInProgress(
  statuses: Record<string, CardStatusInfo>
): boolean {
  return Object.values(statuses).some((info) => info.captionStatus === 'PROCESSING');
}
