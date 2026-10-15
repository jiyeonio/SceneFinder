import React, { useEffect, useState } from 'react';
import {
  Bookmark,
  Clock3,
  Library,
  Play,
  Search,
  Trash2,
} from 'lucide-react';

import { SearchResultItem, VideoMetadata } from '../types';
import { formatTime } from '../utils/formatters';
import { API_BASE_URL } from '../services/searchApi';

type LibraryTab = 'saved' | 'recent';

interface LibraryViewProps {
  onOpenSegment: (item: SearchResultItem) => void;
  videosMap: Record<string, VideoMetadata>;
}

interface BackendFavorite {
  favorite_id: string;
  user_id?: string;
  video_id: string;
  start_time: number;
  end_time: number;
  created_at?: string;
}

export const LibraryView: React.FC<LibraryViewProps> = ({
  onOpenSegment,
  videosMap,
}) => {
  const [activeTab, setActiveTab] = useState<LibraryTab>('saved');

  const [savedSegments, setSavedSegments] = useState<SearchResultItem[]>([]);
  const [recentSegments, setRecentSegments] = useState<SearchResultItem[]>([]);

  // 같은 구간이 DB에 여러 번 저장된 경우까지 처리하기 위해
  // key 하나당 favorite_id 배열을 저장
  const [favoriteIds, setFavoriteIds] = useState<Record<string, string[]>>({});

  // 저장한 구간(DB) + 최근 본 구간(localStorage) 불러오기
  useEffect(() => {
    const loadLibraryData = async () => {
      try {
        const localSaved = JSON.parse(
          localStorage.getItem('scenefinder-saved-segments') || '[]'
        ) as SearchResultItem[];

        const recent = JSON.parse(
          localStorage.getItem('scenefinder-recent-segments') || '[]'
        ) as SearchResultItem[];

        setRecentSegments(recent);

        const accessToken = localStorage.getItem('scenefinder-access-token');

        // 로그인 토큰이 없으면 기존 localStorage 데이터 사용
        if (!accessToken) {
          setSavedSegments(localSaved);
          return;
        }

        const response = await fetch(
          `${API_BASE_URL}/api/users/me/favorites`,
          {
            method: 'GET',
            headers: {
              Authorization: `Bearer ${accessToken}`,
            },
          }
        );

        if (!response.ok) {
          console.error(
            '즐겨찾기 조회 실패:',
            response.status,
            await response.text()
          );

          // 조회 실패 시 기존 localStorage 데이터 유지
          setSavedSegments(localSaved);
          return;
        }

        const data = await response.json();

        console.log('백엔드 즐겨찾기 조회 성공:', data);

        const backendFavorites: BackendFavorite[] = Array.isArray(data.favorites)
          ? data.favorites
          : [];

        // DB favorite_id들을 구간별로 저장
        const favoriteIdMap: Record<string, string[]> = {};

        backendFavorites.forEach((favorite) => {
          if (!favorite.favorite_id) return;

          const key = `${favorite.video_id}-${Number(
            favorite.start_time
          )}-${Number(favorite.end_time)}`;

          if (!favoriteIdMap[key]) {
            favoriteIdMap[key] = [];
          }

          favoriteIdMap[key].push(favorite.favorite_id);
        });

        setFavoriteIds(favoriteIdMap);

        // 백엔드에 실제 존재하는 즐겨찾기만
        // localStorage의 상세 검색 결과와 연결
        const syncedSaved = localSaved.filter((localItem) =>
          backendFavorites.some(
            (favorite) =>
              favorite.video_id === localItem.video_id &&
              Number(favorite.start_time) ===
                Number(localItem.start_time) &&
              Number(favorite.end_time) ===
                Number(localItem.end_time)
          )
        );

        setSavedSegments(syncedSaved);
      } catch (error) {
        console.error('라이브러리 데이터를 불러오는 중 오류:', error);

        try {
          const localSaved = JSON.parse(
            localStorage.getItem('scenefinder-saved-segments') || '[]'
          ) as SearchResultItem[];

          setSavedSegments(localSaved);
        } catch {
          setSavedSegments([]);
        }
      }
    };

    loadLibraryData();
  }, []);

  // 저장한 구간 삭제
  const handleDeleteSavedSegment = async (segmentId: string) => {
    const segment = savedSegments.find(
      (item) => item.segment_id === segmentId
    );

    if (!segment) return;

    const accessToken = localStorage.getItem('scenefinder-access-token');

    if (!accessToken) {
      alert('로그인 후 이용해주세요.');
      return;
    }

    const key = `${segment.video_id}-${Number(
      segment.start_time
    )}-${Number(segment.end_time)}`;

    const ids = favoriteIds[key];

    if (!ids || ids.length === 0) {
      alert('즐겨찾기 정보를 찾을 수 없습니다.');
      return;
    }

    try {
      // 같은 구간이 테스트 과정에서 여러 번 저장됐다면 전부 삭제
      const responses = await Promise.all(
        ids.map((favoriteId) =>
          fetch(
            `${API_BASE_URL}/api/users/me/favorites/${favoriteId}`,
            {
              method: 'DELETE',
              headers: {
                Authorization: `Bearer ${accessToken}`,
              },
            }
          )
        )
      );

      const failed = responses.some((response) => !response.ok);

      if (failed) {
        console.error('일부 즐겨찾기 삭제 실패');
        alert('저장한 구간 삭제에 실패했습니다.');
        return;
      }

      const updated = savedSegments.filter(
        (item) => item.segment_id !== segmentId
      );

      setSavedSegments(updated);

      localStorage.setItem(
        'scenefinder-saved-segments',
        JSON.stringify(updated)
      );

      setFavoriteIds((prev) => {
        const next = { ...prev };
        delete next[key];
        return next;
      });

      console.log('즐겨찾기 삭제 성공');
    } catch (error) {
      console.error('즐겨찾기 삭제 중 오류:', error);
      alert('저장한 구간 삭제 중 오류가 발생했습니다.');
    }
  };

  // 최근 본 구간 삭제
  const handleDeleteRecentSegment = (segmentId: string) => {
    const updated = recentSegments.filter(
      (item) => item.segment_id !== segmentId
    );

    setRecentSegments(updated);

    localStorage.setItem(
      'scenefinder-recent-segments',
      JSON.stringify(updated)
    );
  };

  // 구간 카드
  const renderSegmentCard = (
    segment: SearchResultItem,
    type: 'saved' | 'recent'
  ) => {
    const video = videosMap[segment.video_id];

    return (
      <div
        key={segment.segment_id}
        className="bg-white border border-slate-200 rounded-2xl overflow-hidden hover:shadow-md transition-shadow"
      >
        {/* 썸네일 */}
        <div className="relative aspect-video bg-slate-100 overflow-hidden">
          {video?.thumbnailUrl ? (
            <img
              src={video.thumbnailUrl}
              alt={video.title}
              className="w-full h-full object-cover"
            />
          ) : (
            <div className="w-full h-full flex items-center justify-center text-slate-400">
              <Play className="w-8 h-8" />
            </div>
          )}

          {/* 구간 시간 */}
          <div className="absolute bottom-3 left-3 bg-black/75 text-white text-xs font-mono px-2.5 py-1 rounded-lg">
            {formatTime(segment.start_time)}
            {' - '}
            {formatTime(segment.end_time)}
          </div>

          {/* 관련도 */}
          <div className="absolute top-3 right-3 bg-white/95 text-blue-600 text-xs font-semibold px-2.5 py-1 rounded-lg shadow-sm">
            관련도 {Math.round(segment.score * 100)}%
          </div>
        </div>

        {/* 카드 내용 */}
        <div className="p-4">
          <h2 className="font-bold text-slate-900 line-clamp-2">
            {video?.title || segment.video_id}
          </h2>

          {video && (
            <p className="text-xs text-slate-500 mt-1">
              {video.channelName}
            </p>
          )}

          <div className="mt-4 flex items-center justify-between">
            <button
              type="button"
              onClick={() => onOpenSegment(segment)}
              className="flex items-center gap-1.5 text-sm font-semibold text-blue-600 hover:text-blue-700 cursor-pointer"
            >
              <Play className="w-4 h-4 fill-blue-600" />
              {formatTime(segment.start_time)}부터 보기
            </button>

            <button
              type="button"
              onClick={() => {
                if (type === 'saved') {
                  handleDeleteSavedSegment(segment.segment_id);
                } else {
                  handleDeleteRecentSegment(segment.segment_id);
                }
              }}
              className="p-2 rounded-lg text-slate-400 hover:text-red-500 hover:bg-red-50 transition-colors"
              title={type === 'saved' ? '저장 삭제' : '기록 삭제'}
            >
              <Trash2 className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>
    );
  };

  return (
    <main className="flex-1 bg-[#F8FAFC]">
      <div className="max-w-6xl mx-auto px-6 py-10">

        {/* Page title */}
        <div className="mb-8">
          <div className="flex items-center gap-2 mb-2">
            <Library className="w-6 h-6 text-blue-600" />

            <h1 className="text-2xl font-bold text-slate-900">
              내 라이브러리
            </h1>
          </div>

          <p className="text-sm text-slate-500">
            저장한 영상 구간과 최근 본 구간을 한곳에서 확인하세요.
          </p>
        </div>

        {/* Tabs */}
        <div className="flex items-center gap-2 border-b border-slate-200 mb-8">
          <button
            type="button"
            onClick={() => setActiveTab('saved')}
            className={`flex items-center gap-2 px-4 py-3 text-sm font-semibold border-b-2 transition-colors ${
              activeTab === 'saved'
                ? 'border-blue-600 text-blue-600'
                : 'border-transparent text-slate-500 hover:text-slate-800'
            }`}
          >
            <Bookmark className="w-4 h-4" />
            저장한 구간

            {savedSegments.length > 0 && (
              <span className="ml-1 min-w-5 h-5 px-1.5 rounded-full bg-blue-100 text-blue-600 text-[11px] flex items-center justify-center">
                {savedSegments.length}
              </span>
            )}
          </button>

          <button
            type="button"
            onClick={() => setActiveTab('recent')}
            className={`flex items-center gap-2 px-4 py-3 text-sm font-semibold border-b-2 transition-colors ${
              activeTab === 'recent'
                ? 'border-blue-600 text-blue-600'
                : 'border-transparent text-slate-500 hover:text-slate-800'
            }`}
          >
            <Clock3 className="w-4 h-4" />
            최근 본 구간

            {recentSegments.length > 0 && (
              <span className="ml-1 min-w-5 h-5 px-1.5 rounded-full bg-blue-100 text-blue-600 text-[11px] flex items-center justify-center">
                {recentSegments.length}
              </span>
            )}
          </button>
        </div>

        {/* 저장한 구간 */}
        {activeTab === 'saved' && (
          <>
            {savedSegments.length === 0 ? (
              <div className="bg-white border border-slate-200 rounded-2xl py-16 px-6 text-center">
                <div className="w-14 h-14 mx-auto mb-4 rounded-2xl bg-blue-50 flex items-center justify-center">
                  <Bookmark className="w-6 h-6 text-blue-600" />
                </div>

                <h2 className="text-lg font-bold text-slate-900 mb-2">
                  아직 저장한 구간이 없어요
                </h2>

                <p className="text-sm text-slate-500 max-w-md mx-auto">
                  검색 결과에서 원하는 영상 구간을 찾은 뒤 저장하면
                  이곳에서 다시 확인할 수 있어요.
                </p>

                <div className="mt-6 inline-flex items-center gap-2 text-sm font-medium text-blue-600">
                  <Search className="w-4 h-4" />
                  원하는 장면을 검색해보세요
                </div>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                {savedSegments.map((segment) =>
                  renderSegmentCard(segment, 'saved')
                )}
              </div>
            )}
          </>
        )}

        {/* 최근 본 구간 */}
        {activeTab === 'recent' && (
          <>
            {recentSegments.length === 0 ? (
              <div className="bg-white border border-slate-200 rounded-2xl py-16 px-6 text-center">
                <div className="w-14 h-14 mx-auto mb-4 rounded-2xl bg-blue-50 flex items-center justify-center">
                  <Clock3 className="w-6 h-6 text-blue-600" />
                </div>

                <h2 className="text-lg font-bold text-slate-900 mb-2">
                  아직 최근 본 구간이 없어요
                </h2>

                <p className="text-sm text-slate-500 max-w-md mx-auto">
                  검색 결과에서 영상 구간을 재생하면 최근 본 기록이
                  이곳에 표시됩니다.
                </p>

                <div className="mt-6 inline-flex items-center gap-2 text-sm font-medium text-blue-600">
                  <Play className="w-4 h-4" />
                  검색 결과를 재생해보세요
                </div>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                {recentSegments.map((segment) =>
                  renderSegmentCard(segment, 'recent')
                )}
              </div>
            )}
          </>
        )}

      </div>
    </main>
  );
};