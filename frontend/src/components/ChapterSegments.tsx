import React from 'react';
import { Chapter } from '../types';
import { formatTime } from '../utils/formatters';

interface ChapterSegmentsProps {
  chapters: Chapter[];
  currentTime: number;
  onSelectTimestamp: (timestamp: number) => void;
}

export const ChapterSegments: React.FC<ChapterSegmentsProps> = ({
  chapters,
  currentTime,
  onSelectTimestamp,
}) => {
  if (!chapters || chapters.length === 0) return null;

  return (
    <div className="mt-6">
      <h3 className="text-sm font-bold text-slate-800 mb-3 flex items-center gap-2">
        <span>주요 타임 탐색하기</span>
        <span className="text-xs font-normal text-slate-400">
          (클릭 시 해당 구간으로 바로 이동)
        </span>
      </h3>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {chapters.map((chapter, idx) => {
          // Check if current video time is around this chapter
          const nextChapterTime = chapters[idx + 1] ? chapters[idx + 1].timestamp : Infinity;
          const isActive = currentTime >= chapter.timestamp && currentTime < nextChapterTime;

          return (
            <button
              key={idx}
              id={`chapter-item-${idx}`}
              onClick={() => onSelectTimestamp(chapter.timestamp)}
              className={`text-left p-3 rounded-xl border transition-all cursor-pointer ${
                isActive
                  ? 'border-blue-600 bg-blue-50/60 ring-1 ring-blue-500/20 shadow-xs'
                  : 'border-slate-200 hover:border-blue-300 hover:bg-slate-50/80 bg-white'
              }`}
            >
              <div
                className={`text-xs font-bold font-mono tracking-tight mb-1 ${
                  isActive ? 'text-blue-600' : 'text-slate-700'
                }`}
              >
                {formatTime(chapter.timestamp)}
              </div>
              <div
                className={`text-xs leading-snug line-clamp-2 ${
                  isActive ? 'font-semibold text-slate-900' : 'text-slate-600'
                }`}
                title={chapter.title}
              >
                {chapter.title}
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
};
