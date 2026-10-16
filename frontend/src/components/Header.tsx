import React, { useEffect, useRef } from 'react';
import { Play, Search, Mic, X, User } from 'lucide-react';

interface HeaderProps {
  currentView: 'home' | 'player' | 'browse' | 'auth' | 'library';
  searchQuery: string;
  onSearchQueryChange?: (val: string) => void;
  onSearchSubmit?: () => void;
  onNavigateHome: () => void;
  onNavigateBrowse?: () => void;
  onNavigateAuth?: () => void;
  onNavigateLibrary?: () => void;
  onLogout?: () => void;
  user?: {
    name: string;
    email: string;
  } | null;
}

export const Header: React.FC<HeaderProps> = ({
  currentView,
  searchQuery,
  onSearchQueryChange,
  onSearchSubmit,
  onNavigateHome,
  onNavigateBrowse,
  onNavigateAuth,
  onNavigateLibrary,
  onLogout,
  user,
}) => {
  // 실제 헤더 높이를 CSS 변수(--header-h)로 알려서, 헤더 아래 고정 영역이 정확히 맞도록 함
  const headerRef = useRef<HTMLElement>(null);

  useEffect(() => {
    const header = headerRef.current;
    if (!header) return;

    const update = () =>
      document.documentElement.style.setProperty(
        '--header-h',
        `${header.getBoundingClientRect().height}px`
      );

    update();
    const observer = new ResizeObserver(update);
    observer.observe(header);
    return () => observer.disconnect();
  }, []);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && onSearchSubmit) {
      e.preventDefault();
      onSearchSubmit();
    }
  };

  return (
    <header ref={headerRef} className="sticky top-0 z-30 bg-white border-b border-slate-200/80 px-4 sm:px-8 py-3 transition-colors">
      <div className="max-w-7xl mx-auto flex items-center justify-between gap-4">

        {/* Logo and primary nav */}
        <div className="flex items-center gap-8">
          <button
            id="brand-logo-btn"
            onClick={onNavigateHome}
            className="flex items-center gap-2.5 group text-left focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 rounded-lg cursor-pointer"
          >
            <div className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center text-white shadow-sm shadow-blue-500/20 group-hover:bg-blue-700 transition-colors">
              <Play className="w-4 h-4 fill-white ml-0.5" />
            </div>

            <span className="text-lg font-bold text-slate-900 tracking-tight flex items-center">
              <span>Scene</span>
              <span className="text-blue-600">Finder</span>
            </span>
          </button>

          {(currentView === 'home' ||
            currentView === 'browse' ||
            currentView === 'library') && (
            <nav className="hidden md:flex items-center gap-6 text-sm font-medium">

              {/* 홈 */}
              <button
                onClick={onNavigateHome}
                className={`transition-colors relative py-1 cursor-pointer ${
                  currentView === 'home'
                    ? "text-blue-600 font-semibold after:content-[''] after:absolute after:bottom-0 after:left-0 after:w-full after:h-0.5 after:bg-blue-600"
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                홈
              </button>

              {/* 내 라이브러리 */}
              <button
                onClick={onNavigateLibrary}
                className={`transition-colors relative py-1 cursor-pointer ${
                  currentView === 'library'
                    ? "text-blue-600 font-semibold after:content-[''] after:absolute after:bottom-0 after:left-0 after:w-full after:h-0.5 after:bg-blue-600"
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                내 라이브러리
              </button>

            </nav>
          )}
        </div>

        {/* Player 화면의 검색창 */}
        {currentView === 'player' && (
          <div className="flex-1 max-w-2xl mx-4">
            <div className="relative flex items-center w-full">
              <Search className="absolute left-3.5 w-4 h-4 text-slate-400 pointer-events-none" />

              <input
                id="header-search-input"
                type="text"
                value={searchQuery}
                onChange={(e) => onSearchQueryChange?.(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="어떤 장면을 찾고 있나요?"
                className="w-full bg-slate-50 hover:bg-slate-100/80 focus:bg-white text-slate-900 text-sm rounded-xl pl-10 pr-20 py-2 border border-slate-200 focus:border-blue-500 focus:ring-2 focus:ring-blue-100 transition-all outline-none"
              />

              <div className="absolute right-2.5 flex items-center gap-1.5">
                {searchQuery && (
                  <button
                    onClick={() => onSearchQueryChange?.('')}
                    className="p-1 text-slate-400 hover:text-slate-600 rounded-full"
                    title="검색어 지우기"
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                )}

                <button
                  type="button"
                  className="p-1 text-slate-400 hover:text-slate-600"
                  title="음성 검색"
                >
                  <Mic className="w-3.5 h-3.5" />
                </button>

                <button
                  onClick={onSearchSubmit}
                  className="text-[11px] font-medium text-slate-500 bg-white border border-slate-200 rounded px-1.5 py-0.5 shadow-2xs hover:bg-slate-50 hover:text-blue-600 transition-colors flex items-center gap-0.5"
                  title="검색 실행 (Enter)"
                >
                  ↵ Enter
                </button>
              </div>
            </div>
          </div>
        )}

        {/* 프로필 / 로그인 상태 */}
<div className="flex items-center gap-3">
  {user ? (
    <>
      <span className="hidden sm:inline text-sm font-semibold text-slate-800">
  {user.name}님
</span>

      <button
        type="button"
        onClick={onLogout}
        className="text-sm font-medium text-slate-500 hover:text-blue-600 transition-colors cursor-pointer"
      >
        로그아웃
      </button>
    </>
  ) : (
    <button
      id="user-profile-avatar"
      type="button"
      onClick={onNavigateAuth}
      className="w-8 h-8 rounded-full bg-slate-300 text-white flex items-center justify-center border border-white shadow-2xs ring-1 ring-slate-200 cursor-pointer hover:bg-slate-400 hover:ring-slate-300 transition-all shrink-0"
      title="로그인"
    >
      <User className="w-4 h-4" />
    </button>
  )}
</div>

      </div>
    </header>
  );
};