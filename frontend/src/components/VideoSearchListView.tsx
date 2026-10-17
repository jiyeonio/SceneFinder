import React from 'react';
import { CardAnalysisState, SearchCard } from '../types';
import { formatTime } from '../utils/formatters';
import {
  Play,
  LoaderCircle,
  Search,
  Sparkles,
  Info,
  AlertTriangle,
  SearchX,
} from 'lucide-react';
import { AnalysisStatusBadge } from './AnalysisStatusBadge';
import { AnalysisLoadingScreen } from './AnalysisLoadingScreen';

interface VideoSearchListViewProps {
  cards: SearchCard[];
  // YouTube 검색 응답을 기다리는 중
  isLoading: boolean;
  // 카드별 AI 분석 상태를 갱신하는 중
  isAnalyzing: boolean;
  pollingNotice: string | null;
  searchQuery: string;
  onSelectCard: (card: SearchCard) => void;
  // 분석 전 카드를 눌렀을 때의 분석 로딩 화면 상태
  cardAnalysis?: CardAnalysisState | null;
  onPlayCardFromStart?: () => void;
  onCancelCardAnalysis?: () => void;
}

const PENDING_MESSAGES: Record<
  Exclude<SearchCard['status'], 'done' | 'checking'>,
  string
> = {
  idle: '아직 분석하지 않은 영상입니다.',
  queued: '분석 대기 중입니다.',
  analyzing: '검색어와 관련된 구간을 분석하고 있습니다.',
  no_results: '검색어와 관련된 구간을 찾지 못했습니다.',
  failed: '이 영상은 분석하지 못했습니다.',
};

export const VideoSearchListView: React.FC<VideoSearchListViewProps> = ({
  cards,
  isLoading,
  isAnalyzing,
  pollingNotice,
  searchQuery,
  onSelectCard,
  cardAnalysis = null,
  onPlayCardFromStart,
  onCancelCardAnalysis,
}) => {
  const doneCount = cards.filter((card) => card.status === 'done').length;
  const activeCount = cards.filter(
    (card) => card.status === 'queued' || card.status === 'analyzing'
  ).length;

  return (
    <main className="min-h-[calc(100vh-61px)] bg-[#F8FAFC] px-4 py-8 sm:px-6">
      <div className="mx-auto max-w-5xl">

        {/* 검색 제목 */}
        <div className="mb-7">
          <h1 className="text-2xl font-bold text-slate-900">
            영상 검색 결과
          </h1>

          <p className="mt-2 text-sm text-slate-500">
            검색어: {searchQuery}
          </p>
        </div>

        {/* 분석 전 카드를 누른 경우: 분석 로딩 화면 */}
        {cardAnalysis && (
          <CardAnalysisScreen
            analysis={cardAnalysis}
            onPlayFromStart={onPlayCardFromStart}
            onBack={onCancelCardAnalysis}
          />
        )}

        {/* YouTube 영상 검색 중 */}
        {!cardAnalysis && cards.length === 0 && isLoading && (
          <AnalysisLoadingScreen
            title="영상 검색 중..."
            description="검색어와 관련된 영상을 찾고 있습니다."
          />
        )}

        {/* 검색 결과 없음 */}
        {!cardAnalysis && cards.length === 0 && !isLoading && (
          <div className="flex min-h-[300px] flex-col items-center justify-center rounded-2xl border border-slate-200 bg-white p-8 text-center">
            <Search className="mb-4 h-10 w-10 text-slate-400" />

            <h2 className="text-lg font-bold text-slate-800">
              검색 결과가 없습니다
            </h2>

            <p className="mt-2 text-sm text-slate-500">
              다른 검색어로 다시 검색해 보세요.
            </p>
          </div>
        )}

        {/* YouTube 검색 목록 + 카드별 분석 상태 */}
        {!cardAnalysis && cards.length > 0 && (
          <>
            <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
              <span
                data-testid="search-summary"
                className="text-sm font-semibold text-slate-600"
              >
                영상 {cards.length}개 · 분석 완료 {doneCount}개
              </span>

              {isAnalyzing && activeCount > 0 && (
                <span className="flex items-center gap-2 text-xs font-medium text-blue-600">
                  <LoaderCircle className="h-4 w-4 animate-spin" />
                  {activeCount}개 영상 분석 중...
                </span>
              )}
            </div>

            {pollingNotice && (
              <div
                role="status"
                className="mb-4 flex items-start gap-2 rounded-xl border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800"
              >
                <Info className="mt-0.5 h-4 w-4 shrink-0" />
                {pollingNotice}
              </div>
            )}

            <div className="space-y-4">
              {/* YouTube 검색 순서 고정: 분석이 끝나도 카드 내용만 갱신 */}
              {cards.map((card) => (
                <VideoCard
                  key={card.youtubeVideoId}
                  card={card}
                  onSelect={onSelectCard}
                />
              ))}
            </div>
          </>
        )}
      </div>
    </main>
  );
};

const VideoCard: React.FC<{
  card: SearchCard;
  onSelect: (card: SearchCard) => void;
}> = ({ card, onSelect }) => {
  const { video, status, reason, segments } = card;
  const best = segments[0];
  const isDone = status === 'done' && best !== undefined;

  return (
    <button
      type="button"
      data-testid="video-card"
      data-youtube-id={card.youtubeVideoId}
      data-status={status}
      onClick={() => onSelect(card)}
      className="group flex w-full flex-col gap-4 rounded-2xl border border-slate-200 bg-white p-4 text-left transition-colors hover:border-blue-300 hover:shadow-md sm:flex-row"
    >
      {/* 영상 썸네일 */}
      <div className="relative aspect-video w-full shrink-0 overflow-hidden rounded-xl bg-slate-100 sm:w-64">
        <img
          src={video.thumbnailUrl}
          alt={video.title}
          className="h-full w-full object-cover transition-transform duration-300 group-hover:scale-105"
        />

        {/* AI가 찾은 시작 시간 */}
        {isDone && (
          <span className="absolute left-2 top-2 inline-flex items-center gap-1 rounded bg-blue-600 px-2 py-1 text-xs font-semibold text-white">
            <Sparkles className="h-3 w-3" />
            {formatTime(best.start_time)}
          </span>
        )}

        {/* 영상 길이 */}
        {video.totalDuration > 0 && (
          <span className="absolute bottom-2 right-2 rounded bg-black/80 px-2 py-1 text-xs font-semibold text-white">
            {formatTime(video.totalDuration)}
          </span>
        )}

        {/* 마우스를 올리면 재생 버튼 표시 */}
        <div className="absolute inset-0 flex items-center justify-center bg-black/20 opacity-0 transition-opacity group-hover:opacity-100">
          <div className="flex h-12 w-12 items-center justify-center rounded-full bg-white/90">
            <Play className="h-5 w-5 fill-slate-900 text-slate-900" />
          </div>
        </div>
      </div>

      {/* 영상 정보 */}
      <div className="flex min-w-0 flex-1 flex-col justify-center">
        <div className="flex items-start justify-between gap-3">
          <h2 className="line-clamp-2 text-base font-bold leading-snug text-slate-900 group-hover:text-blue-600 sm:text-lg">
            {video.title}
          </h2>

          <AnalysisStatusBadge status={status} reason={reason} captionStatus={card.captionStatus} />
        </div>

        <p className="mt-2 text-sm text-slate-500">
          {video.channelName}
          {video.totalDuration > 0 && (
            <span> · {formatTime(video.totalDuration)}</span>
          )}
        </p>

        {/* AI 분석 영역: 상태가 바뀌어도 카드 높이가 크게 변하지 않도록 고정 높이 */}
        <div className="mt-4 min-h-[76px]">
          {isDone ? (
            <>
              <div className="flex flex-wrap items-center gap-2">
                <span className="inline-flex items-center gap-1 rounded-full bg-blue-50 px-3 py-1 text-xs font-semibold text-blue-700">
                  <Sparkles className="h-3.5 w-3.5" />
                  AI 검색 구간 {segments.length}개
                </span>

                <span className="text-xs text-slate-500">
                  최고 관련도 {best.score.toFixed(3)}
                </span>
              </div>

              <p className="mt-3 text-sm text-slate-600">
                가장 관련 있는 구간:{' '}
                <span className="font-semibold text-blue-600">
                  {formatTime(best.start_time)}
                  {' - '}
                  {formatTime(best.end_time)}
                </span>
              </p>

              <p className="mt-2 text-xs font-semibold text-blue-600">
                클릭하여 해당 구간부터 재생 →
              </p>
            </>
          ) : status === 'checking' ? (
            // 분석 상태를 아직 모를 때: 상태를 추측하지 않고 자리만 표시
            <div className="space-y-2.5 pt-1" aria-label="분석 상태 확인 중">
              <div className="h-3 w-2/5 animate-pulse rounded bg-slate-100" />
              <div className="h-3 w-3/5 animate-pulse rounded bg-slate-100" />
            </div>
          ) : (
            <>
              <p className="text-sm text-slate-500">
                {PENDING_MESSAGES[status === 'done' ? 'no_results' : status]}
              </p>

              <p className="mt-2 text-xs font-semibold text-slate-400">
                {status === 'idle'
                  ? '클릭하면 이 영상을 분석합니다 →'
                  : status === 'queued' || status === 'analyzing'
                    ? '클릭하면 이 영상을 먼저 분석합니다 →'
                    : '클릭하여 다시 확인 →'}
              </p>
            </>
          )}
        </div>
      </div>
    </button>
  );
};

// 분석 로딩 화면 (기존 로딩 박스 재사용): 로딩 → 완료 시 App에서 자동 재생,
// 실패/결과 없음 → 안내 + 처음부터 재생 옵션
const CardAnalysisScreen: React.FC<{
  analysis: CardAnalysisState;
  onPlayFromStart?: () => void;
  onBack?: () => void;
}> = ({ analysis, onPlayFromStart, onBack }) => {
  const { card, phase, status, message } = analysis;

  const backButton = onBack && (
    <button
      type="button"
      onClick={onBack}
      className="rounded-lg border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50"
    >
      목록으로
    </button>
  );

  const videoInfo = (
    <div className="mt-6 flex max-w-md items-center gap-3 text-left">
      <img
        src={card.video.thumbnailUrl}
        alt={card.video.title}
        className="aspect-video w-28 shrink-0 rounded-lg object-cover"
      />
      <div className="min-w-0">
        <p className="line-clamp-2 text-sm font-semibold text-slate-800">
          {card.video.title}
        </p>
        <p className="mt-1 text-xs text-slate-500">
          {card.video.channelName}
          {card.video.totalDuration > 0 &&
            ` · ${formatTime(card.video.totalDuration)}`}
        </p>
      </div>
    </div>
  );

  if (phase === 'loading') {
    return (
      <AnalysisLoadingScreen
        title={status === 'queued' ? '분석 대기 중...' : '구간 분석 중...'}
        description={
          status === 'queued' ? (
            '앞선 영상 분석이 끝나면 시작합니다'
          ) : (
            <>
              이 영상에서 검색어와 관련된 구간을 찾고 있습니다.
              <br />
              분석이 끝나면 가장 관련 있는 구간부터 자동으로 재생합니다.
            </>
          )
        }
      >
        {videoInfo}
        <div className="mt-6">{backButton}</div>
      </AnalysisLoadingScreen>
    );
  }

  const failed = phase === 'failed';

  return (
    <AnalysisLoadingScreen
      icon={
        failed ? (
          <AlertTriangle className="mb-5 h-12 w-12 text-red-500" />
        ) : (
          <SearchX className="mb-5 h-12 w-12 text-amber-500" />
        )
      }
      title={
        failed ? '영상 분석에 실패했습니다' : '관련 구간을 찾지 못했습니다'
      }
      description={
        failed
          ? message || '영상 분석에 실패했습니다.'
          : '분석은 끝났지만 검색어와 관련된 구간이 없습니다.'
      }
    >
      <div className="mt-4">
        <AnalysisStatusBadge status={failed ? 'failed' : 'no_results'} />
      </div>
      {videoInfo}
      <div className="mt-6 flex flex-wrap justify-center gap-2">
        {onPlayFromStart && (
          <button
            type="button"
            onClick={onPlayFromStart}
            className="inline-flex items-center gap-1.5 rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700"
          >
            <Play className="h-4 w-4 fill-white" />
            처음부터 재생
          </button>
        )}
        {backButton}
      </div>
    </AnalysisLoadingScreen>
  );
};
