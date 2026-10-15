import React, { useState } from 'react';
import { Search, Laptop, FlaskConical, Home as HomeIcon, Trophy, ArrowRight, Play } from 'lucide-react';
import { SHOWCASE_VIDEOS } from '../data/mockData';

interface BrowseViewProps {
  onSearch: (query: string, targetVideoId?: string) => void;
}

export const BrowseView: React.FC<BrowseViewProps> = ({
  onSearch,
}) => {
  const [selectedCategory, setSelectedCategory] = useState<string>('all');

  const categories = [
    { id: 'all', label: '전체 영상' },
    { id: '제품 리뷰', label: '제품 리뷰' },
    { id: '교육 · 실험', label: '교육 · 실험' },
    { id: '일상 · 브이로그', label: '일상 · 브이로그' },
    { id: '스포츠 경기', label: '스포츠 경기' },
  ];

  const filteredVideos = selectedCategory === 'all'
    ? SHOWCASE_VIDEOS
    : SHOWCASE_VIDEOS.filter((v) => v.category === selectedCategory);

  const getCategoryIcon = (iconName: string) => {
    switch (iconName) {
      case 'Laptop':
        return <Laptop className="w-3.5 h-3.5" />;
      case 'FlaskConical':
        return <FlaskConical className="w-3.5 h-3.5" />;
      case 'Home':
        return <HomeIcon className="w-3.5 h-3.5" />;
      case 'Trophy':
        return <Trophy className="w-3.5 h-3.5" />;
      default:
        return <Play className="w-3.5 h-3.5" />;
    }
  };

  return (
    <div className="w-full flex-1 max-w-7xl mx-auto px-4 sm:px-8 py-8">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-slate-200">
        <div>
          <div className="flex items-center gap-2 text-xs font-bold text-blue-600 uppercase tracking-wider mb-1">
            <span className="w-1.5 h-3.5 bg-blue-600 rounded-xs" />
            <span>AI INDEXED VIDEOS</span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-bold text-slate-900 tracking-tight">
            검색 가능한 영상 둘러보기
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            SceneFinder로 사전에 인덱싱되어 자연어 검색이 지원되는 비디오 목록입니다.
          </p>
        </div>
      </div>

      {/* Category Filter Chips */}
      <div className="flex items-center gap-2 py-6 overflow-x-auto no-scrollbar">
        {categories.map((cat) => (
          <button
            key={cat.id}
            onClick={() => setSelectedCategory(cat.id)}
            className={`px-4 py-2 rounded-xl text-xs font-semibold whitespace-nowrap transition-all cursor-pointer ${
              selectedCategory === cat.id
                ? 'bg-blue-600 text-white shadow-xs'
                : 'bg-white text-slate-600 border border-slate-200 hover:border-slate-300 hover:bg-slate-50'
            }`}
          >
            {cat.label}
          </button>
        ))}
      </div>

      {/* Video Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
        {filteredVideos.map((item) => (
          <div
            key={item.videoId}
            id={`browse-card-${item.videoId}`}
            onClick={() => onSearch(item.query, item.videoId)}
            className="group bg-white rounded-2xl border border-slate-200/90 overflow-hidden shadow-2xs hover:shadow-md hover:border-blue-400 transition-all cursor-pointer flex flex-col"
          >
            {/* Thumbnail */}
            <div className="relative aspect-video w-full bg-slate-100 overflow-hidden">
              <img
                src={item.thumbnailUrl}
                alt={item.title}
                className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
              />
              <div className="absolute top-2.5 left-2.5">
                <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md bg-blue-600/90 backdrop-blur-xs text-white text-[11px] font-medium shadow-xs">
                  {getCategoryIcon(item.categoryIcon)}
                  <span>{item.category}</span>
                </span>
              </div>
            </div>

            {/* Content */}
            <div className="p-4 flex-1 flex flex-col justify-between">
              <div>
                <h3 className="text-sm font-bold text-slate-900 line-clamp-2 leading-snug group-hover:text-blue-600 transition-colors">
                  {item.title}
                </h3>
                <p className="text-xs text-slate-500 mt-2 line-clamp-2">
                  추천 검색: <span className="font-medium text-slate-700">"{item.query}"</span>
                </p>
              </div>

              <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between text-xs text-blue-600 font-semibold">
                <span>구간 검색 시작하기</span>
                <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-1 transition-transform" />
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
