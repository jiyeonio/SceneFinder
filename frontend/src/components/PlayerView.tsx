import React, { useState } from 'react';
import { Home, Search } from 'lucide-react';
import { VideoMetadata, SearchResultItem, SearchCard } from '../types';
import { VideoPlayer } from './VideoPlayer';
import { ChapterSegments } from './ChapterSegments';
import { SearchResultsList } from './SearchResultsList';

interface PlayerViewProps {
  currentVideo: VideoMetadata;
  selectedSegment: SearchResultItem | null;
  // 현재 영상의 모든 AI 구간 (플레이어 아래 타임라인/구간 목록)
  currentSegments: SearchResultItem[];
  onSelectSegment: (item: SearchResultItem) => void;
  // 오른쪽 목록: 검색된 영상 카드 (YouTube 순서)
  cards: SearchCard[];
  onSelectCard: (card: SearchCard) => void;
  isLoading: boolean;
  searchQuery: string;
  onNavigateHome: () => void;
  onSelectSuggestion: (query: string) => void;
  // 검색 결과 목록으로 돌아가기
  onBackToList?: () => void;
}

export const PlayerView: React.FC<PlayerViewProps> = ({
  currentVideo,
  selectedSegment,
  currentSegments,
  onSelectSegment,
  cards,
  onSelectCard,
  isLoading,
  searchQuery,
  onNavigateHome,
  onSelectSuggestion,
  onBackToList,
}) => {
  const [currentVideoTime, setCurrentVideoTime] = useState<number>(selectedSegment?.start_time || 0);
  const [targetSeekTime, setTargetSeekTime] = useState<number | null>(null);

  const handleSelectChapterTimestamp = (timestamp: number) => {
    setTargetSeekTime(timestamp);
  };

  const handleSeekHandled = () => {
    setTargetSeekTime(null);
  };

  return (
    <div className="w-full min-h-[calc(100vh-61px)] flex bg-[#F8FAFC]">
      {/* Left Slim Sidebar (Matches screenshot 2) */}
      <aside className="hidden md:flex flex-col items-center w-16 xl:w-48 bg-white border-r border-slate-200/80 p-3 pt-6 shrink-0">
        <nav className="w-full space-y-1.5">
          <button
            id="sidebar-home-btn"
            onClick={onNavigateHome}
            className="w-full flex items-center justify-center xl:justify-start gap-3 px-3 py-2.5 rounded-xl text-slate-600 hover:text-slate-900 hover:bg-slate-50 transition-colors text-xs font-semibold cursor-pointer"
            title="홈으로 가기"
          >
            <Home className="w-4 h-4 text-slate-500 shrink-0" />
            <span className="hidden xl:inline">홈</span>
          </button>

          <button
            id="sidebar-search-btn"
            onClick={onBackToList}
            title="검색 결과 목록으로"
            className="w-full flex items-center justify-center xl:justify-start gap-3 px-3 py-2.5 rounded-xl bg-blue-50 text-blue-600 font-bold text-xs cursor-pointer hover:bg-blue-100"
          >
            <Search className="w-4 h-4 text-blue-600 shrink-0" />
            <span className="hidden xl:inline">검색</span>
          </button>
        </nav>
      </aside>

      {/* Main Container */}
      <main className="flex-1 min-w-0 p-4 sm:p-6 lg:p-8 max-w-7xl mx-auto w-full">
        {/* Two Column Layout: Player Column (Left) & Search Results Column (Right) */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 lg:gap-8 items-start">
          {/* Left: Video Player, Title, Segment Timeline, Chapters (7 or 8 cols) */}
          <div className="min-w-0 lg:col-span-8 bg-white rounded-2xl p-4 sm:p-6 border border-slate-200/90 shadow-2xs">
            <VideoPlayer
              video={currentVideo}
              selectedSegment={selectedSegment}
              onTimeUpdate={(time) => setCurrentVideoTime(time)}
              targetSeekTime={targetSeekTime}
              onSeekHandled={handleSeekHandled}
              segments={currentSegments}
              onSelectSegment={onSelectSegment}
            />

            {/* Same Video other Chapters / Moments */}
            <ChapterSegments
              chapters={currentVideo.chapters}
              currentTime={currentVideoTime}
              onSelectTimestamp={handleSelectChapterTimestamp}
            />
          </div>

          {/* Right: Search Results List (4 or 5 cols) */}
          <div className="min-w-0 lg:col-span-4 bg-white rounded-2xl p-4 sm:p-5 border border-slate-200/90 shadow-2xs sticky top-20">
            <SearchResultsList
              cards={cards}
              currentYoutubeId={currentVideo.youtube_video_id ?? null}
              onSelectCard={onSelectCard}
              isLoading={isLoading}
              searchQuery={searchQuery}
              onSelectSuggestion={onSelectSuggestion}
            />
          </div>
        </div>
      </main>
    </div>
  );
};
