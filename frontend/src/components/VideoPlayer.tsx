
import React, { useEffect, useRef, useState } from 'react';
import {
  Share2,
  Bookmark,
  Target,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';
import { VideoMetadata, SearchResultItem } from '../types';
import { formatDate, formatTime } from '../utils/formatters';
import { API_BASE_URL } from '../services/searchApi';

interface VideoPlayerProps {
  video: VideoMetadata;
  selectedSegment: SearchResultItem | null;
  onTimeUpdate?: (currentTime: number) => void;
  targetSeekTime: number | null;
  onSeekHandled: () => void;
  // 이 영상에서 AI가 찾은 모든 구간 (타임라인 마커 + 구간 칩 목록)
  segments?: SearchResultItem[];
  onSelectSegment?: (item: SearchResultItem) => void;
}

interface YouTubePlayerInstance {
  playVideo: () => void;
  pauseVideo: () => void;
  seekTo: (seconds: number, allowSeekAhead: boolean) => void;
  getCurrentTime: () => number;
  getDuration: () => number;
  mute: () => void;
  unMute: () => void;
  destroy: () => void;
}

interface YouTubePlayerEvent {
  data: number;
}

interface YouTubeAPI {
  Player: new (
    element: HTMLElement,
    options: {
      videoId: string;
      width?: string | number;
      height?: string | number;
      playerVars?: Record<string, number>;
      events?: {
        onReady?: () => void;
        onStateChange?: (event: YouTubePlayerEvent) => void;
        onError?: (event: YouTubePlayerEvent) => void;
      };
    }
  ) => YouTubePlayerInstance;
}

declare global {
  interface Window {
    YT?: YouTubeAPI;
    onYouTubeIframeAPIReady?: () => void;
  }
}

let youtubeApiPromise: Promise<YouTubeAPI> | null = null;

function loadYouTubeAPI(): Promise<YouTubeAPI> {
  if (window.YT?.Player) {
    return Promise.resolve(window.YT);
  }

  if (youtubeApiPromise) {
    return youtubeApiPromise;
  }

  youtubeApiPromise = new Promise((resolve, reject) => {
    const previousCallback = window.onYouTubeIframeAPIReady;

    window.onYouTubeIframeAPIReady = () => {
      previousCallback?.();

      if (window.YT?.Player) {
        resolve(window.YT);
      } else {
        reject(new Error('YouTube API를 불러오지 못했습니다.'));
      }
    };

    const existingScript = document.querySelector(
      'script[src="https://www.youtube.com/iframe_api"]'
    );

    if (!existingScript) {
      const script = document.createElement('script');
      script.src = 'https://www.youtube.com/iframe_api';
      script.async = true;

      script.onerror = () => {
        youtubeApiPromise = null;
        reject(new Error('YouTube API 스크립트 로딩 실패'));
      };

      document.head.appendChild(script);
    }
  });

  return youtubeApiPromise;
}

export const VideoPlayer: React.FC<VideoPlayerProps> = ({
  video,
  selectedSegment,
  onTimeUpdate,
  targetSeekTime,
  onSeekHandled,
  segments = [],
  onSelectSegment,
}) => {
  const videoRef = useRef<HTMLVideoElement>(null);
  const chipListRef = useRef<HTMLDivElement>(null);
  const youtubeContainerRef = useRef<HTMLDivElement>(null);
  const youtubePlayerRef = useRef<YouTubePlayerInstance | null>(null);

  const onTimeUpdateRef = useRef(onTimeUpdate);
  const selectedSegmentRef = useRef(selectedSegment);
  const onSeekHandledRef = useRef(onSeekHandled);
  const pendingSeekRef = useRef<number | null>(null);

 const isYouTube  = Boolean(video.youtube_video_id);

  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(video.totalDuration || 0);
  const [isSaved, setIsSaved] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [showShareToast, setShowShareToast] = useState(false);
  const [playerError, setPlayerError] = useState('');

  useEffect(() => {
    onTimeUpdateRef.current = onTimeUpdate;
  }, [onTimeUpdate]);

  useEffect(() => {
    selectedSegmentRef.current = selectedSegment;
  }, [selectedSegment]);

  useEffect(() => {
    onSeekHandledRef.current = onSeekHandled;
  }, [onSeekHandled]);

  const seekToTime = (seconds: number, play = true) => {
    const safeTime = Math.max(0, seconds);

    if (isYouTube) {
      const player = youtubePlayerRef.current;

      if (!player) {
        pendingSeekRef.current = safeTime;
        return;
      }

      player.seekTo(safeTime, true);

      if (play) {
        player.playVideo();
      }
    } else if (videoRef.current) {
      videoRef.current.currentTime = safeTime;

      if (play) {
        videoRef.current.play().catch(console.error);
      }
    }

    setCurrentTime(safeTime);
    onTimeUpdateRef.current?.(safeTime);
  };

  // YouTube 플레이어 생성
  useEffect(() => {
    if (!isYouTube || !video.youtube_video_id) {
      return;
    }

    let cancelled = false;
    let intervalId: ReturnType<typeof setInterval> | null = null;
    let createdPlayer: YouTubePlayerInstance | null = null;

    const container = youtubeContainerRef.current;

    if (!container) return;

    setPlayerError('');
    setDuration(0);

    const initialTime = selectedSegmentRef.current?.start_time || 0;
    pendingSeekRef.current = initialTime;
    setCurrentTime(initialTime);

    loadYouTubeAPI()
      .then((YT) => {
        if (cancelled || !container.isConnected) return;

        
const playerMount = document.createElement('div');
container.appendChild(playerMount);

createdPlayer = new YT.Player(playerMount, {
          videoId: video.youtube_video_id!,
          // 플레이어 박스(16:9)를 꽉 채우도록 (기본값 640x360 고정 크기 방지)
          width: '100%',
          height: '100%',
          playerVars: {
            autoplay: 0,
            controls: 1,
            playsinline: 1,
            rel: 0,
            origin: window.location.origin ? 0 : 0,
          },
          events: {
            onReady: () => {
              if (cancelled || !createdPlayer) return;

              youtubePlayerRef.current = createdPlayer;

              const startTime = pendingSeekRef.current ?? 0;
              pendingSeekRef.current = null;

              createdPlayer.seekTo(startTime, true);

              setCurrentTime(startTime);
              setDuration(createdPlayer.getDuration() || 0);

              // 사용자가 카드/구간을 눌러 열었으므로 0초 시작이어도 바로 재생
              createdPlayer.playVideo();

              intervalId = setInterval(() => {
                if (!createdPlayer || cancelled) return;

                try {
                  const time = createdPlayer.getCurrentTime();
                  const total = createdPlayer.getDuration();

                  if (Number.isFinite(time)) {
                    setCurrentTime(time);
                    onTimeUpdateRef.current?.(time);
                  }

                  if (Number.isFinite(total) && total > 0) {
                    setDuration(total);
                  }
                } catch {
                  // 플레이어가 종료되는 중이면 무시
                }
              }, 500);
            },
            onError: (event) => {
              if (cancelled) return;

              console.error('YouTube 재생 오류:', event.data);
              setPlayerError(
                '이 YouTube 영상은 재생할 수 없습니다. 영상의 임베드 허용 여부를 확인해주세요.'
              );
            },
          },
        });
      })
      .catch((error) => {
        if (cancelled) return;

        console.error('YouTube 플레이어 오류:', error);
        setPlayerError('YouTube 플레이어를 불러오지 못했습니다.');
      });

    return () => {
      cancelled = true;

      if (intervalId) {
        clearInterval(intervalId);
      }

      youtubePlayerRef.current = null;

      if (createdPlayer) {
        try {
          createdPlayer.destroy();
        } catch {
          // 이미 종료된 플레이어
        }
      }
    };
  }, [isYouTube, video.youtube_video_id]);

  // 검색 결과에서 다른 구간 선택 시 해당 시점으로 이동
  useEffect(() => {
    if (!selectedSegment) return;
    if (selectedSegment.video_id !== video.video_id) return;

    seekToTime(selectedSegment.start_time);
  }, [
    selectedSegment?.segment_id,
    selectedSegment?.start_time,
    video.video_id,
  ]);

  // ChapterSegments에서 요청한 시간 이동
  useEffect(() => {
    if (targetSeekTime === null) return;

    seekToTime(targetSeekTime);
    onSeekHandledRef.current();
  }, [targetSeekTime]);

  // 현재 구간 칩이 가로 스크롤 목록 안에서 보이도록 맞춤
  useEffect(() => {
    const list = chipListRef.current;
    const chip = list?.querySelector<HTMLElement>('[data-current="true"]');
    if (!list || !chip) return;

    const left = chip.offsetLeft - list.offsetLeft;
    if (left < list.scrollLeft || left + chip.offsetWidth > list.scrollLeft + list.clientWidth) {
      list.scrollTo({ left: left - 16, behavior: 'smooth' });
    }
  }, [selectedSegment?.segment_id]);

  // 저장된 구간 여부 확인
  useEffect(() => {
    if (!selectedSegment) {
      setIsSaved(false);
      return;
    }

    try {
      const saved = JSON.parse(
        localStorage.getItem('scenefinder-saved-segments') || '[]'
      ) as SearchResultItem[];

      setIsSaved(
        saved.some(
          (item) => item.segment_id === selectedSegment.segment_id
        )
      );
    } catch {
      setIsSaved(false);
    }
  }, [selectedSegment]);

  // 기존 즐겨찾기 저장 기능 유지
  
const handleSaveSegment = async () => {
  if (!selectedSegment || isSaving) return;

  const accessToken = localStorage.getItem('scenefinder-access-token');

  if (!accessToken) {
    alert('로그인 후 이용해주세요.');
    return;
  }

  setIsSaving(true);

  const apiBaseUrl = API_BASE_URL;

  const headers = {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${accessToken}`,
  };

  try {
    const saved = JSON.parse(
      localStorage.getItem('scenefinder-saved-segments') || '[]'
    ) as SearchResultItem[];

    // 서버에 실제 저장되어 있는 즐겨찾기 조회
    const listResponse = await fetch(
      `${apiBaseUrl}/api/users/me/favorites`,
      { headers }
    );

    if (!listResponse.ok) {
      throw new Error(`즐겨찾기 조회 실패: ${listResponse.status}`);
    }

    const listData = await listResponse.json();

    // 응답이 배열이거나 favorites 배열을 포함하는 형태 지원
    const favorites = Array.isArray(listData)
      ? listData
      : Array.isArray(listData.favorites)
        ? listData.favorites
        : null;

    if (!favorites) {
      throw new Error('즐겨찾기 목록 응답 형식을 확인해야 합니다.');
    }

    const existingFavorite = favorites.find(
      (item: {
        favorite_id?: string;
        video_id: string;
        start_time: number;
        end_time: number;
      }) =>
        item.video_id === selectedSegment.video_id &&
        Number(item.start_time) === Number(selectedSegment.start_time) &&
        Number(item.end_time) === Number(selectedSegment.end_time)
    );

    if (isSaved) {
      // 저장 취소: 서버 DB에서도 실제 삭제
      if (existingFavorite) {
        if (!existingFavorite.favorite_id) {
          throw new Error('삭제할 favorite_id가 없습니다.');
        }

        const deleteResponse = await fetch(
          `${apiBaseUrl}/api/users/me/favorites/${existingFavorite.favorite_id}`,
          {
            method: 'DELETE',
            headers,
          }
        );

        if (!deleteResponse.ok) {
          throw new Error(`즐겨찾기 삭제 실패: ${deleteResponse.status}`);
        }
      }

      const updated = saved.filter(
        (item) => item.segment_id !== selectedSegment.segment_id
      );

      localStorage.setItem(
        'scenefinder-saved-segments',
        JSON.stringify(updated)
      );

      setIsSaved(false);
      return;
    }

    // 이미 DB에 저장된 구간이면 중복 POST 요청을 보내지 않음
    if (!existingFavorite) {
      const response = await fetch(
        `${apiBaseUrl}/api/users/me/favorites`,
        {
          method: 'POST',
          headers,
          body: JSON.stringify({
            video_id: selectedSegment.video_id,
            start_time: selectedSegment.start_time,
            end_time: selectedSegment.end_time,
          }),
        }
      );

      if (!response.ok) {
        throw new Error(`즐겨찾기 저장 실패: ${response.status}`);
      }
    }

    const updated = [
      selectedSegment,
      ...saved.filter(
        (item) => item.segment_id !== selectedSegment.segment_id
      ),
    ];

    localStorage.setItem(
      'scenefinder-saved-segments',
      JSON.stringify(updated)
    );

    setIsSaved(true);
  } catch (error) {
    console.error('구간 저장 처리 오류:', error);
    alert('구간 저장 처리 중 오류가 발생했습니다.');
  } finally {
    setIsSaving(false);
  }
};

  // 전체 길이: YouTube API의 영상 길이(정수 초)를 우선 사용해 YouTube 플레이어 표시와 일치시킴
  // (플레이어 getDuration()은 744.341처럼 소수라 내림하면 1초 어긋날 수 있음)
  const totalVideoDuration =
    video.totalDuration > 0 ? video.totalDuration : duration > 0 ? duration : 0;

  const handleTimelineClick = (
    event: React.MouseEvent<HTMLDivElement>
  ) => {
    if (totalVideoDuration <= 0) return;

    const rect = event.currentTarget.getBoundingClientRect();
    const ratio = Math.max(
      0,
      Math.min(1, (event.clientX - rect.left) / rect.width)
    );

    seekToTime(ratio * totalVideoDuration);
  };

  const handleJumpToSegment = () => {
    if (!selectedSegment) return;
    seekToTime(selectedSegment.start_time);
  };

  const handleShare = async () => {
    const url = isYouTube && video.youtube_video_id
      ? `https://www.youtube.com/watch?v=${video.youtube_video_id}&t=${Math.floor(
          selectedSegment?.start_time ?? currentTime
        )}s`
      : window.location.href;

    try {
      await navigator.clipboard.writeText(url);
      setShowShareToast(true);
      setTimeout(() => setShowShareToast(false), 2500);
    } catch {
      alert('링크 복사에 실패했습니다.');
    }
  };



  const currentProgressPercent = totalVideoDuration > 0
    ? Math.min(100, (currentTime / totalVideoDuration) * 100)
    : 0;

  // 이 영상의 구간들을 시간 순으로 (라이브러리에서 연 구간처럼 목록에 없으면 함께 표시)
  const timelineSegments = [...segments];
  if (
    selectedSegment &&
    selectedSegment.video_id === video.video_id &&
    !timelineSegments.some((s) => s.segment_id === selectedSegment.segment_id)
  ) {
    timelineSegments.push(selectedSegment);
  }
  timelineSegments.sort((a, b) => a.start_time - b.start_time);

  const currentIndex = selectedSegment
    ? timelineSegments.findIndex(
        (s) => s.segment_id === selectedSegment.segment_id
      )
    : -1;

  const toPercent = (seconds: number) =>
    totalVideoDuration > 0
      ? Math.max(0, Math.min(100, (seconds / totalVideoDuration) * 100))
      : 0;

  const selectSegment = (item: SearchResultItem) => {
    if (onSelectSegment) {
      onSelectSegment(item);
    } else {
      seekToTime(item.start_time);
    }
  };

  // 이전/다음 구간 (현재 구간이 없으면 현재 재생 위치 기준)
  const prevSegment =
    currentIndex >= 0
      ? timelineSegments[currentIndex - 1]
      : [...timelineSegments].reverse().find((s) => s.start_time < currentTime - 1);
  const nextSegment =
    currentIndex >= 0
      ? timelineSegments[currentIndex + 1]
      : timelineSegments.find((s) => s.start_time > currentTime + 1);

  return (
    <div className="w-full flex flex-col">
      {/* 영상 플레이어 */}
      <div className="relative w-full aspect-video bg-black rounded-2xl overflow-hidden shadow-sm border border-slate-200/60">
        {isYouTube ? (
          <div className="w-full h-full">
            <div
              key={video.youtube_video_id}
              ref={youtubeContainerRef}
              className="w-full h-full [&_iframe]:block [&_iframe]:h-full [&_iframe]:w-full"
            />
          </div>
        ) : (
          <video
            ref={videoRef}
            src={video.videoUrl}
            poster={video.thumbnailUrl}
            className="w-full h-full object-contain"
            controls
            playsInline
            onTimeUpdate={(event) => {
              const time = event.currentTarget.currentTime;
              setCurrentTime(time);
              onTimeUpdateRef.current?.(time);
            }}
            onLoadedMetadata={(event) => {
              const player = event.currentTarget;
              setDuration(player.duration || 0);

              if (selectedSegmentRef.current) {
                player.currentTime =
                  selectedSegmentRef.current.start_time;
              }
            }}
          />
        )}

        {playerError && (
          <div className="absolute inset-0 bg-black/90 flex flex-col items-center justify-center text-white text-center p-6 gap-3">
            <p className="text-sm">{playerError}</p>
            {video.youtube_video_id && (
              <a
                href={`https://www.youtube.com/watch?v=${video.youtube_video_id}`}
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-300 underline text-sm"
              >
                YouTube에서 열기
              </a>
            )}
          </div>
        )}
      </div>

      {/* 영상 제목 및 정보 */}
      <div className="mt-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 pb-4 border-b border-slate-100">
        <div>
          <h1 className="text-xl font-bold text-slate-900 tracking-tight leading-snug">
            {video.title}
          </h1>

          <p className="text-xs text-slate-500 mt-1">
            <span className="font-semibold text-slate-700">
              {video.channelName}
            </span>

            {video.publishDate && (
              <span> · {formatDate(video.publishDate)}</span>
            )}

            {video.views && (
              <span> · 조회수 {video.views}</span>
            )}
          </p>
        </div>

        <div className="flex items-center gap-2 relative">
          <button
            onClick={handleShare}
            className="flex shrink-0 items-center gap-1.5 whitespace-nowrap px-3 py-1.5 rounded-lg border border-slate-200 hover:bg-slate-50 text-slate-700 text-xs font-medium"
          >
            <Share2 className="w-3.5 h-3.5" />
            공유
          </button>

<button
  onClick={handleSaveSegment}
  disabled={!selectedSegment || isSaving}
  className={`flex shrink-0 items-center gap-1.5 whitespace-nowrap px-3 py-1.5 rounded-lg border text-xs font-medium disabled:opacity-40 ${
    isSaved
      ? 'border-blue-600 bg-blue-50 text-blue-600'
      : 'border-slate-200 hover:bg-slate-50 text-slate-700'
  }`}
>
  <Bookmark
    className={`w-3.5 h-3.5 ${
      isSaved ? 'fill-blue-600' : ''
    }`}
  />
  {isSaving ? '저장 중...' : isSaved ? '저장됨' : '저장'}
</button>

          {showShareToast && (
            <div className="absolute right-0 -top-8 bg-slate-900 text-white text-xs px-2.5 py-1 rounded shadow-md whitespace-nowrap">
              링크가 복사되었습니다!
            </div>
          )}
        </div>
      </div>

      {/* AI 검색 구간 타임라인: 이 영상의 모든 구간을 마커로 표시, 현재 구간 강조 */}
      <div className="mt-4 p-4 rounded-xl bg-slate-50/70 border border-slate-200/90">
        <div className="flex flex-wrap items-center justify-between gap-2 mb-3 text-xs">
          <div className="flex min-w-0 flex-wrap items-center gap-2">
            <div className="w-5 h-5 shrink-0 rounded-full bg-red-100 text-red-600 flex items-center justify-center">
              <Target className="w-3 h-3" />
            </div>

            <span className="font-semibold text-slate-800 whitespace-nowrap">
              검색된 구간 {timelineSegments.length}개
            </span>

            {selectedSegment && currentIndex >= 0 ? (
              <button
                onClick={handleJumpToSegment}
                title="현재 구간 처음으로"
                className="font-mono font-bold text-blue-600 hover:underline bg-blue-50 px-2 py-0.5 rounded border border-blue-200/60 whitespace-nowrap"
              >
                {formatTime(selectedSegment.start_time)} -{' '}
                {formatTime(selectedSegment.end_time)}
              </button>
            ) : (
              <span className="text-slate-500">
                {timelineSegments.length > 0 ? '구간을 선택하세요' : '검색 구간 없음'}
              </span>
            )}
          </div>

          <div className="flex shrink-0 items-center gap-1.5">
            <button
              type="button"
              data-testid="prev-segment"
              onClick={() => prevSegment && selectSegment(prevSegment)}
              disabled={!prevSegment}
              title="이전 구간"
              className="inline-flex items-center gap-0.5 rounded-md border border-slate-200 bg-white px-2 py-1 font-semibold text-slate-700 hover:border-blue-300 hover:text-blue-600 disabled:opacity-40 disabled:hover:border-slate-200 disabled:hover:text-slate-700"
            >
              <ChevronLeft className="w-3.5 h-3.5" />
              이전
            </button>
            <button
              type="button"
              data-testid="next-segment"
              onClick={() => nextSegment && selectSegment(nextSegment)}
              disabled={!nextSegment}
              title="다음 구간"
              className="inline-flex items-center gap-0.5 rounded-md border border-slate-200 bg-white px-2 py-1 font-semibold text-slate-700 hover:border-blue-300 hover:text-blue-600 disabled:opacity-40 disabled:hover:border-slate-200 disabled:hover:text-slate-700"
            >
              다음
              <ChevronRight className="w-3.5 h-3.5" />
            </button>
            <span className="ml-1 font-mono text-slate-500 whitespace-nowrap">
              전체{' '}
              {totalVideoDuration > 0
                ? formatTime(totalVideoDuration)
                : '--:--'}
            </span>
          </div>
        </div>

        <div
          data-testid="segment-timeline"
          className="relative w-full h-3 bg-slate-200 rounded-full cursor-pointer"
          onClick={handleTimelineClick}
          title="클릭하여 시간 이동"
        >
          <div
            className="absolute left-0 top-0 bottom-0 bg-slate-300 rounded-full"
            style={{ width: `${currentProgressPercent}%` }}
          />

          {totalVideoDuration > 0 &&
            timelineSegments.map((item, index) => {
              const isCurrent = index === currentIndex;
              const left = toPercent(item.start_time);
              const width = Math.max(1, toPercent(item.end_time) - left);

              return (
                <button
                  key={item.segment_id}
                  type="button"
                  data-testid="segment-marker"
                  data-current={isCurrent}
                  aria-label={`구간 ${formatTime(item.start_time)} - ${formatTime(item.end_time)}`}
                  title={`${formatTime(item.start_time)} - ${formatTime(item.end_time)} · Score ${item.score.toFixed(3)}`}
                  onClick={(event) => {
                    event.stopPropagation();
                    selectSegment(item);
                  }}
                  className={`absolute top-0 bottom-0 rounded-full transition-colors ${
                    isCurrent
                      ? 'z-10 bg-blue-600 ring-2 ring-blue-300'
                      : 'bg-blue-300 hover:bg-blue-500'
                  }`}
                  style={{ left: `${left}%`, width: `${width}%` }}
                />
              );
            })}

          <div
            className="pointer-events-none absolute z-20 top-1/2 -translate-y-1/2 -translate-x-1/2 w-3.5 h-3.5 bg-white border-2 border-blue-600 rounded-full shadow-md"
            style={{ left: `${currentProgressPercent}%` }}
          />
        </div>

        {/* 같은 영상의 구간 목록 (시간 순, 많으면 가로 스크롤) */}
        {timelineSegments.length > 0 && (
          <div
            ref={chipListRef}
            data-testid="segment-chips"
            className="mt-3 flex gap-2 overflow-x-auto pb-1"
          >
            {timelineSegments.map((item, index) => {
              const isCurrent = index === currentIndex;

              return (
                <button
                  key={item.segment_id}
                  type="button"
                  data-testid="segment-chip"
                  data-current={isCurrent}
                  onClick={() => selectSegment(item)}
                  title={`Score ${item.score.toFixed(3)}`}
                  className={`shrink-0 whitespace-nowrap rounded-full border px-3 py-1 font-mono text-xs font-semibold transition-colors ${
                    isCurrent
                      ? 'border-blue-600 bg-blue-600 text-white'
                      : 'border-slate-200 bg-white text-slate-700 hover:border-blue-300 hover:text-blue-600'
                  }`}
                >
                  {formatTime(item.start_time)} - {formatTime(item.end_time)}
                </button>
              );
            })}
          </div>
        )}

        <p className="text-[11px] text-slate-500 mt-2.5">
          AI가 찾은 구간은 타임라인 위에 파란색으로 표시됩니다.
          마커나 구간 시간을 클릭하면 해당 장면으로 이동합니다.
        </p>
      </div>
    </div>
  );
};
