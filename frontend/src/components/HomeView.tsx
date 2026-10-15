import React, { useState } from 'react';
import { Search } from 'lucide-react';
import { RECOMMENDED_QUERIES } from '../data/mockData';

interface HomeViewProps {
  initialQuery: string;
  onSearch: (query: string, targetVideoId?: string) => void;
}

export const HomeView: React.FC<HomeViewProps> = ({
  initialQuery,
  onSearch,
}) => {
  const [inputVal, setInputVal] = useState(initialQuery);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (inputVal.trim()) {
      onSearch(inputVal.trim());
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      if (inputVal.trim()) {
        onSearch(inputVal.trim());
      }
    }
  };



  return (
    <div className="w-full flex flex-col items-center">
      {/* Hero Section */}
      <section className="w-full max-w-4xl mx-auto pt-14 sm:pt-20 pb-12 px-4 text-center flex flex-col items-center">
        {/* Pill Badge */}
        <div className="inline-flex items-center gap-1.5 px-3.5 py-1 rounded-full bg-blue-50 border border-blue-100 text-blue-600 text-xs font-medium mb-6 shadow-2xs">
          <span>✦ AI Video Moment Search</span>
        </div>

        {/* Main Headline */}
        <h1 className="text-3xl sm:text-5xl font-black text-slate-900 tracking-tight leading-[1.2] sm:leading-[1.15] max-w-2xl">
          <span>영상 속 그 순간,</span>
          <br />
          <span className="text-blue-600">검색으로 바로 만나보세요.</span>
        </h1>

        {/* Subtitle Description */}
        <p className="mt-5 text-sm sm:text-base text-slate-600 max-w-xl leading-relaxed">
          장르에 상관없이 원하는 장면이나 내용을 자연어로 검색하면<br className="hidden sm:inline" /> AI가 관련된 영상 구간을 찾아줍니다.
        </p>

        {/* Big Natural Language Search Bar */}
        <form
          onSubmit={handleSubmit}
          className="w-full max-w-2xl mt-8 relative"
        >
          <div className="relative flex items-center bg-white rounded-2xl border border-slate-200/90 shadow-sm hover:border-blue-400 focus-within:border-blue-600 focus-within:ring-4 focus-within:ring-blue-100 transition-all p-1.5 sm:p-2">
            <div className="pl-3.5 pr-2 text-slate-400">
              <Search className="w-5 h-5" />
            </div>

            <input
              id="home-search-input"
              type="text"
              value={inputVal}
              onChange={(e) => setInputVal(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="어떤 장면을 찾고 있나요?"
              className="flex-1 bg-transparent text-slate-900 text-sm sm:text-base outline-none placeholder:text-slate-400 py-2 pr-2"
              autoFocus
            />

            <div className="hidden sm:flex items-center text-xs text-slate-400 font-mono px-2 py-0.5 bg-slate-50 border border-slate-200/60 rounded-md mr-1">
              ⌘K
            </div>

            <button
              id="home-search-btn"
              type="submit"
              className="flex items-center justify-center gap-1.5 px-4 sm:px-5 py-2.5 sm:py-3 bg-blue-600 hover:bg-blue-700 active:bg-blue-800 text-white text-xs sm:text-sm font-semibold rounded-xl transition-all shadow-xs shrink-0 cursor-pointer whitespace-nowrap"
            >
              <span>구간 찾기 →</span>
            </button>
          </div>
        </form>

        {/* Recommended Search Examples ("추천 검색:") */}
        <div className="w-full max-w-3xl mt-5 flex flex-wrap items-center justify-center gap-2 text-xs">
          <span className="text-slate-500 font-medium flex items-center gap-1 mr-1">
            <span className="text-blue-500">📍</span> 추천 검색:
          </span>
          {RECOMMENDED_QUERIES.map((queryText) => (
            <button
              key={queryText}
              type="button"
              onClick={() => {
                setInputVal(queryText);
                onSearch(queryText);
              }}
              className="inline-flex items-center gap-1 px-3 py-1.5 rounded-full bg-white hover:bg-blue-50/80 text-slate-700 hover:text-blue-600 border border-slate-200 hover:border-blue-300 transition-colors shadow-2xs text-xs font-normal cursor-pointer"
            >
              <span>{queryText}</span>
              <span className="text-slate-400 text-[10px]">↗</span>
            </button>
          ))}
        </div>
      </section>

  

      {/* Footer */}
      <footer className="w-full max-w-7xl mx-auto px-4 sm:px-8 py-8 mt-12 border-t border-slate-200/80 flex flex-col sm:flex-row items-center justify-between gap-4 text-xs text-slate-500">
        <div>
          © 2025 SceneFinder. Natural Language Video Search & Indexing.
        </div>
        <div className="flex items-center gap-6">
          <button className="hover:text-slate-800 transition-colors cursor-pointer">개인정보처리방침</button>
          <button className="hover:text-slate-800 transition-colors cursor-pointer">이용약관</button>
          <button className="hover:text-slate-800 transition-colors cursor-pointer">문의</button>
        </div>
      </footer>
    </div>
  );
};
