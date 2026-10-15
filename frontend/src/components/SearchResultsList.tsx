import React from 'react';
import { SearchCard } from '../types';
import { formatTime } from '../utils/formatters';
import { Play, AlertCircle, LoaderCircle } from 'lucide-react';
import { AnalysisStatusBadge } from './AnalysisStatusBadge';

// 플레이어 화면 오른쪽: 검색된 영상 목록 (목록 화면과 같은 YouTube 순서, 영상당 카드 1개)
// 같은 영상의 여러 구간은 플레이어 아래 구간 목록에서 보여줍니다.
interface SearchResultsListProps {
  cards: SearchCard[];
  // 지금 재생 중인 영상의 YouTube ID
  currentYoutubeId: string | null;
  onSelectCard: (card: SearchCard) => void;
  isLoading: boolean;
  searchQuery: string;
  onSelectSuggestion?: (query: string) => void;
}

export const SearchResultsList: React.FC<SearchResultsListProps> = ({
  cards,
  currentYoutubeId,
  onSelectCard,
  isLoading,
  searchQuery,
  onSelectSuggestion,
}) => {
  const hasCards = cards.length > 0;

  return (
    <div className="w-full flex flex-col">
      {/* 헤더 */}
      <div className="flex items-center justify-between gap-2 pb-3 mb-3 border-b border-slate-200">
        <div className="flex min-w-0 items-center gap-2">
          <h2 className="shrink-0 text-base font-bold text-slate-900 tracking-tight">
            검색된 영상
          </h2>
          <span className="truncate text-[11px] font-medium text-blue-700 bg-blue-50 px-2 py-0.5 rounded-full">
            YouTube 검색순
          </span>
        </div>

        <span className="shrink-0 text-xs font-semibold text-slate-500">
          {hasCards ? `${cards.length}개 영상` : isLoading ? '검색 중...' : '0개'}
        </span>
      </div>

      {/* 분석 중 안내 */}
      {isLoading && (
        <div
          role="status"
          className="mb-4 flex items-start gap-2.5 rounded-xl border border-blue-100 bg-blue-50/70 p-3"
        >
          <LoaderCircle className="w-4 h-4 shrink-0 animate-spin text-blue-600 mt-0.5" />
          <div>
            <p className="text-xs font-semibold text-blue-800">
              AI 영상 분석 중...
            </p>
            <p className="mt-1 text-[11px] leading-relaxed text-blue-700">
              분석이 끝나는 대로 영상별 상태가 자동으로 갱신됩니다.
            </p>
          </div>
        </div>
      )}

      {/* 아직 영상 목록이 없을 때 */}
      {isLoading && !hasCards && (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="p-3 rounded-xl border border-slate-200 bg-white animate-pulse flex gap-3"
            >
              <div className="w-24 aspect-video bg-slate-200 rounded-lg shrink-0" />
              <div className="flex-1 space-y-2 py-1">
                <div className="h-4 bg-slate-200 rounded w-4/5" />
                <div className="h-3 bg-slate-100 rounded w-1/2" />
              </div>
            </div>
          ))}
        </div>
      )}

      {/* 검색 결과 없음 */}
      {!isLoading && !hasCards && (
        <div className="p-8 text-center bg-white rounded-2xl border border-slate-200/80 shadow-2xs my-4">
          <div className="w-12 h-12 rounded-full bg-slate-100 text-slate-400 flex items-center justify-center mx-auto mb-3">
            <AlertCircle className="w-6 h-6 text-slate-400" />
          </div>
          <h3 className="text-sm font-bold text-slate-800 mb-1">
            다른 영상이 없습니다
          </h3>
          <p className="text-xs text-slate-500 max-w-xs mx-auto mb-4 leading-relaxed">
            {searchQuery
              ? `"${searchQuery}"(으)로 다시 검색하면 관련 영상을 볼 수 있습니다.`
              : '검색어를 입력해 관련 영상을 찾아보세요.'}
          </p>

          {onSelectSuggestion && searchQuery && (
            <button
              onClick={() => onSelectSuggestion(searchQuery)}
              className="text-xs font-semibold text-blue-600 hover:text-blue-800 hover:bg-blue-50/80 py-1 px-2.5 rounded-md transition-colors"
            >
              "{searchQuery}" 다시 검색
            </button>
          )}
        </div>
      )}

      {/* 영상 목록 */}
      {hasCards && (
        <div className="space-y-3">
          {cards.map((card) => (
            <SidebarVideoCard
              key={card.youtubeVideoId}
              card={card}
              isCurrent={card.youtubeVideoId === currentYoutubeId}
              onSelect={onSelectCard}
            />
          ))}
        </div>
      )}
    </div>
  );
};

const SidebarVideoCard: React.FC<{
  card: SearchCard;
  isCurrent: boolean;
  onSelect: (card: SearchCard) => void;
}> = ({ card, isCurrent, onSelect }) => {
  const { video, status, reason, segments } = card;
  const best = segments[0];

  return (
    <button
      type="button"
      data-testid="sidebar-video-card"
      data-youtube-id={card.youtubeVideoId}
      data-status={status}
      data-current={isCurrent || undefined}
      aria-current={isCurrent || undefined}
      onClick={() => onSelect(card)}
      className={`@container group w-full text-left p-3 rounded-xl border transition-all cursor-pointer ${
        isCurrent
          ? 'border-blue-600 bg-blue-50/40 ring-1 ring-blue-500/20 shadow-xs'
          : 'border-slate-200/90 bg-white hover:border-blue-300 hover:bg-slate-50/60 shadow-2xs'
      }`}
    >
      {/* 카드 폭이 좁으면 썸네일 위/정보 아래, 넓으면 좌우 배치 */}
      <div className="flex flex-col gap-2 @min-[15.5rem]:flex-row @min-[15.5rem]:gap-3 @min-[15.5rem]:items-start">
        {/* 썸네일 */}
        <div className="relative w-full @min-[15.5rem]:w-24 @min-[19rem]:w-28 aspect-video rounded-lg overflow-hidden bg-slate-100 shrink-0 border border-slate-200/60">
          <img
            src={video.thumbnailUrl}
            alt={video.title}
            className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
          />

          {video.totalDuration > 0 && (
            <div className="absolute bottom-1 right-1 bg-black/80 text-white text-[10px] font-mono font-medium px-1.5 py-0.5 rounded">
              {formatTime(video.totalDuration)}
            </div>
          )}

          <div className="absolute inset-0 bg-black/20 opacity-0 group-hover:opacity-100 flex items-center justify-center transition-opacity">
            <div className="w-6 h-6 rounded-full bg-white/90 flex items-center justify-center">
              <Play className="w-3 h-3 text-slate-900 fill-slate-900 ml-0.5" />
            </div>
          </div>
        </div>

        {/* 영상 정보 */}
        <div className="min-w-0 flex-1">
          <h4 className="text-xs sm:text-sm font-semibold text-slate-900 line-clamp-2 leading-snug group-hover:text-blue-600 transition-colors">
            {video.title}
          </h4>

          <p className="mt-1 truncate text-[11px] text-slate-500">
            {video.channelName}
          </p>

          {/* 상태 + 구간 정보: 좁으면 줄바꿈되어 카드 밖으로 나가지 않음 */}
          <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
            {isCurrent ? (
              <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-blue-600">
                <span className="w-1.5 h-1.5 rounded-full bg-blue-600 animate-pulse" />
                재생 중
              </span>
            ) : (
              <AnalysisStatusBadge status={status} reason={reason} />
            )}

            {status === 'done' && best && (
              <>
                <span className="whitespace-nowrap text-[11px] text-slate-500">
                  구간 {segments.length}개
                </span>
                <span
                  className="whitespace-nowrap text-[10px] font-mono font-bold text-blue-700 bg-blue-50 px-1.5 py-0.5 rounded-md border border-blue-200/70"
                  title={`가장 관련 있는 구간 ${formatTime(best.start_time)} - ${formatTime(best.end_time)}`}
                >
                  Score {best.score.toFixed(3)}
                </span>
              </>
            )}
          </div>
        </div>
      </div>
    </button>
  );
};
