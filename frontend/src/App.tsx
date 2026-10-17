import { useState, useEffect, useLayoutEffect, useRef, useMemo } from 'react';
import {
  VideoMetadata,
  SearchResultItem,
  CardStatusInfo,
  SearchCard,
  CardAnalysisState,
} from './types';
import {
  searchYouTubeVideos,
  searchMultipleVideos,
  convertMultiSearchResults,
  convertSingleSearchResults,
  getYouTubeVideoStatus,
  searchSingleVideo,
  MultiSearchResponse,
  SingleSearchResponse,
} from './services/searchApi';
import {
  buildSearchCards,
  deriveCardStatuses,
  hasCaptionsInProgress,
  hasUnfinishedCards,
} from './utils/searchCards';
import { Header } from './components/Header';
import { HomeView } from './components/HomeView';
import { PlayerView } from './components/PlayerView';
import { VideoSearchListView } from './components/VideoSearchListView';
import { BrowseView } from './components/BrowseView';
import { AuthView } from './components/AuthView';
import { LibraryView } from './components/LibraryView';

type AppView = 'home' | 'player' | 'browse' | 'auth' | 'library';

interface User {
  name: string;
  email: string;
}

const POLLING_INTERVAL_MS = 3000;
// 서버가 멈춰 PROCESSING이 끝나지 않는 경우를 대비한 자동 갱신 최대 시간
const POLLING_MAX_DURATION_MS = 20 * 60 * 1000;
// 일시적인 네트워크 오류는 이 횟수까지 다시 시도
const POLLING_MAX_CONSECUTIVE_ERRORS = 3;

export default function App() {
  const [currentView, setCurrentView] = useState<AppView>(() => {
    if (typeof window !== 'undefined') {
      const path = window.location.pathname;

      if (path === '/browse') return 'browse';
      if (path === '/search') return 'player';
      if (path === '/login') return 'auth';
      if (path === '/library') return 'library';
    }

    return 'home';
  });

  const [searchQuery, setSearchQuery] = useState<string>('');

// 실제 YouTube 영상 정보 관리
const [videosMap, setVideosMap] =
  useState<Record<string, VideoMetadata>>(() => {
    try {
      const saved = localStorage.getItem('scenefinder-video-metadata');

      return saved ? JSON.parse(saved) : {};
    } catch {
      return {};
    }
  });

  const [searchResults, setSearchResults] = useState<SearchResultItem[]>([]);

  const [selectedSegment, setSelectedSegment] =
    useState<SearchResultItem | null>(null);

  const [currentVideoId, setCurrentVideoId] = useState<string>('abc123');
  const [isLoading, setIsLoading] = useState<boolean>(false);

  // 초기 검색과 백그라운드 분석을 구분
  const [isAnalyzing, setIsAnalyzing] = useState<boolean>(false);

  // YouTube 검색 순서대로의 영상 ID와 카드별 분석 상태
  const [searchVideoIds, setSearchVideoIds] = useState<string[]>([]);
  const [cardStatuses, setCardStatuses] = useState<
    Record<string, CardStatusInfo>
  >({});

  // 자동 갱신이 중간에 멈췄을 때 목록에 보여줄 안내
  const [pollingNotice, setPollingNotice] = useState<string | null>(null);

  // 분석 실패/결과 없음 영상을 '처음부터 재생'으로 보고 있는 영상 (YouTube ID)
  const [previewVideoId, setPreviewVideoId] = useState<string | null>(null);

  // 분석 전 카드를 눌렀을 때의 분석 로딩 화면 상태와 전용 polling
  const [cardAnalysis, setCardAnalysis] = useState<CardAnalysisState | null>(
    null
  );
  const cardAnalysisIdRef = useRef(0);
  const cardAnalysisTimerRef = useRef<ReturnType<typeof setTimeout> | null>(
    null
  );

  // 실제로 검색을 실행한 검색어 (헤더 입력값은 입력 중에 바뀔 수 있음)
  const activeQueryRef = useRef('');

  // 목록 → 플레이어/분석 화면으로 갈 때의 목록 스크롤 위치 (돌아올 때 복원)
  const listScrollRef = useRef(0);
  const restoreListScrollRef = useRef(false);
  // 지금 검색 목록이 화면에 보이는지 (렌더 후 갱신)
  const listVisibleRef = useRef(false);

  // 새로운 검색 또는 화면 이동 시 이전 검색을 무효화
  const searchIdRef = useRef(0);

  // 자동 재검색 타이머 관리
  const pollingTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // 사용자가 직접 선택한 검색 결과를 자동 갱신에서 보호
  const selectedSegmentRef = useRef<SearchResultItem | null>(null);

  // 로그인 사용자 정보 복원
  const [user, setUser] = useState<User | null>(() => {
    if (typeof window === 'undefined') return null;

    const savedUser = localStorage.getItem('scenefinder-user');

    if (!savedUser) return null;

    try {
      return JSON.parse(savedUser);
    } catch {
      return null;
    }
  });

  // 카드 분석 로딩 화면의 polling 중단
  const cancelCardAnalysis = () => {
    cardAnalysisIdRef.current += 1;

    if (cardAnalysisTimerRef.current !== null) {
      clearTimeout(cardAnalysisTimerRef.current);
      cardAnalysisTimerRef.current = null;
    }

    setCardAnalysis(null);
  };

  const stopPolling = () => {
    searchIdRef.current += 1;

    if (pollingTimerRef.current !== null) {
      clearTimeout(pollingTimerRef.current);
      pollingTimerRef.current = null;
    }

    cancelCardAnalysis();
    setIsLoading(false);
    setIsAnalyzing(false);
  };

  // 컴포넌트 종료 시 타이머 정리
  useEffect(() => {
    return () => {
      searchIdRef.current += 1;
      cardAnalysisIdRef.current += 1;

      if (pollingTimerRef.current !== null) {
        clearTimeout(pollingTimerRef.current);
      }

      if (cardAnalysisTimerRef.current !== null) {
        clearTimeout(cardAnalysisTimerRef.current);
      }
    };
  }, []);

  // 브라우저 뒤로가기 / 앞으로가기 처리
  useEffect(() => {
    // 스크롤 복원은 직접 처리 (브라우저 자동 복원과 충돌 방지)
    if ('scrollRestoration' in window.history) {
      window.history.scrollRestoration = 'manual';
    }

    const handlePopState = (event: PopStateEvent) => {
      const path = window.location.pathname;

      if (path !== '/search') {
        stopPolling();
      } else if (event.state?.sceneFinderView !== 'player') {
        // 플레이어에서 뒤로가기: 검색 목록으로 돌아가고 스크롤 복원
        returnToList();
      }

      if (path === '/browse') {
        setCurrentView('browse');
      } else if (path === '/search') {
        setCurrentView('player');
      } else if (path === '/login') {
        setCurrentView('auth');
      } else if (path === '/library') {
        setCurrentView('library');
      } else {
        setCurrentView('home');
      }
    };

    window.addEventListener('popstate', handlePopState);

    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  // 실제 YouTube + AI 다중 영상 검색
  const executeSearch = async (query: string, targetVideoId?: string) => {
    // 검색 결과는 목록에서 사용자가 직접 선택하도록 처리
    void targetVideoId;
    const trimmedQuery = query.trim();

    if (!trimmedQuery) return;

    // 이전 검색과 자동 재검색 중단
    stopPolling();
    const currentSearchId = searchIdRef.current;

    selectedSegmentRef.current = null;

    setSearchQuery(trimmedQuery);
    activeQueryRef.current = trimmedQuery;
    setCurrentView('player');

    if (
      typeof window !== 'undefined' &&
      window.location.pathname !== '/search'
    ) {
      window.history.pushState(null, '', '/search');
    } else if (window.history.state?.sceneFinderView === 'player') {
      // 플레이어에서 새로 검색: 현재 기록을 목록 상태로 바꿔 둠
      window.history.replaceState(null, '', '/search');
    }

    window.scrollTo(0, 0);
    setIsLoading(true);
    setIsAnalyzing(false);
    setSearchResults([]);
    setSelectedSegment(null);
    setPreviewVideoId(null);
    setSearchVideoIds([]);
    setCardStatuses({});
    setPollingNotice(null);

    try {
      // 1. YouTube에서 관련 영상 검색
      const youtubeResponse = await searchYouTubeVideos(trimmedQuery, 20);

      if (currentSearchId !== searchIdRef.current) return;

      const youtubeVideoIds = youtubeResponse.items.map(
        (video) => video.youtube_video_id
      );

      // 2. YouTube 영상 정보를 기존 프론트 형식으로 변환
      const youtubeVideos: Record<string, VideoMetadata> = {};

      for (const video of youtubeResponse.items) {
        youtubeVideos[video.youtube_video_id] = {
          video_id: video.youtube_video_id,
          youtube_video_id: video.youtube_video_id,
          title: video.title,
          category: 'youtube',
          categoryLabel: 'YouTube',
          channelName: video.channel_name,
          publishDate: video.published_at || '',
          views: '',
          thumbnailUrl: video.thumbnail_url,
          videoUrl: `https://www.youtube.com/watch?v=${video.youtube_video_id}`,
          totalDuration: video.duration ?? 0,
          chapters: [],
        };
      }

      setVideosMap((previous) => {
        const updated = {
          ...previous,
          ...youtubeVideos,
        };

        localStorage.setItem(
          'scenefinder-video-metadata',
          JSON.stringify(updated)
        );

        return updated;
      });

      // 3. 분석 결과를 기다리지 않고 YouTube 검색 목록을 바로 표시
      // 첫 분석 상태 응답 전에는 '분석 대기'로 추측하지 않고 '확인 중'으로 표시
      // (추측한 상태가 첫 응답 때 한꺼번에 바뀌어 목록이 다시 바뀌어 보이던 문제)
      let latestStatuses: Record<string, CardStatusInfo> = {};

      for (const id of youtubeVideoIds) {
        latestStatuses[id] = { status: 'checking' };
      }

      setSearchVideoIds(youtubeVideoIds);
      setCardStatuses(latestStatuses);
      setIsLoading(false);

      if (youtubeVideoIds.length === 0) {
        return;
      }

      setIsAnalyzing(true);

      const pollingStartedAt = Date.now();
      let consecutiveErrors = 0;
      let autoAnalysisRequested = false;

      const scheduleNextPoll = () => {
        pollingTimerRef.current = setTimeout(() => {
          pollingTimerRef.current = null;

          if (currentSearchId !== searchIdRef.current) return;

          void pollSearchResults();
        }, POLLING_INTERVAL_MS);
      };

      // 4. 백엔드 응답을 화면에 반영하는 공통 함수
      const applySearchResponse = (
        response: MultiSearchResponse,
        requestedIds: string[]
      ) => {
        if (currentSearchId !== searchIdRef.current) return;

        const { results, videos } = convertMultiSearchResults(response);

        // 분석된 영상 정보에도 YouTube 검색에서 받은 길이를 채워 넣기
        for (const video of Object.values(videos)) {
          const youtubeVideo = video.youtube_video_id
            ? youtubeVideos[video.youtube_video_id]
            : undefined;

          if (youtubeVideo) {
            video.totalDuration = youtubeVideo.totalDuration;
            video.publishDate = youtubeVideo.publishDate;
          }
        }

        setVideosMap((previous) => {
          const updated = {
            ...previous,
            ...videos,
          };

          localStorage.setItem(
            'scenefinder-video-metadata',
            JSON.stringify(updated)
          );

          return updated;
        });

        setSearchResults(results);

        // 이번에 요청한 영상의 상태만 갱신하고,
        // 요청에서 뺀 실패 영상은 이전 상태(실패)를 그대로 유지
        const derived = deriveCardStatuses(requestedIds, response);

        // 분석이 요청 처리 중에 막 끝난 영상은 백엔드가 잠깐 PENDING으로 돌려주므로,
        // '분석 중' → '분석 대기'로 되돌아가며 깜빡이지 않게 유지
        for (const [id, info] of Object.entries(derived)) {
          if (
            (info.status === 'queued' || info.status === 'idle') &&
            latestStatuses[id]?.status === 'analyzing'
          ) {
            derived[id] = latestStatuses[id];
          }
        }

        latestStatuses = {
          ...latestStatuses,
          ...derived,
        };
        setCardStatuses(latestStatuses);

        // 검색 결과가 갱신되어도 자동으로 첫 번째 영상을 선택하지 않음
        // 사용자가 직접 선택한 구간만 갱신된 결과에서 유지
        if (selectedSegmentRef.current) {
          const previousSelection = selectedSegmentRef.current;

          const preservedItem = results.find(
            (item) =>
              item.segment_id === previousSelection.segment_id &&
              item.video_id === previousSelection.video_id
          );

          if (preservedItem) {
            selectedSegmentRef.current = preservedItem;
            setSelectedSegment(preservedItem);
          }
        }

        console.log('AI 다중 검색 결과:', response);

        // 분석 대기/분석 중인 영상이 남아 있을 때만 계속 갱신.
        // 화면 설명을 만드는 중인 영상이 있으면 '분석 중' 표시 없이 결과만 계속 갱신
        const stillAnalyzing = hasUnfinishedCards(latestStatuses);
        const captionsInProgress = hasCaptionsInProgress(latestStatuses);

        if (!stillAnalyzing) {
          setIsAnalyzing(false);
          if (!captionsInProgress) return;
        }

        if (Date.now() - pollingStartedAt > POLLING_MAX_DURATION_MS) {
          setIsAnalyzing(false);
          // 화면 설명만 남은 경우는 자막 검색 결과가 이미 있으므로 안내 없이 멈춤
          if (!stillAnalyzing) return;
          setPollingNotice(
            '분석이 오래 걸려 자동 갱신을 멈췄습니다. 다시 검색하면 최신 상태를 확인할 수 있습니다.'
          );
          return;
        }

        scheduleNextPoll();
      };

      // 5. 동일한 검색 조건으로 3초마다 재조회 (실패한 영상은 제외)
      const pollSearchResults = async () => {
        if (currentSearchId !== searchIdRef.current) return;

        const requestedIds = youtubeVideoIds.filter(
          (id) => latestStatuses[id]?.status !== 'failed'
        );

        try {
          // 자동 분석은 검색의 첫 요청에서만 시작 (최대 AUTO_ANALYZE_COUNT개).
          // 이후 요청은 상태/결과만 확인해서 YouTube 다운로드 요청을 늘리지 않음
          const response = await searchMultipleVideos(
            trimmedQuery,
            requestedIds,
            3,
            !autoAnalysisRequested
          );
          autoAnalysisRequested = true;

          if (currentSearchId !== searchIdRef.current) return;

          consecutiveErrors = 0;
          applySearchResponse(response, requestedIds);
        } catch (error) {
          if (currentSearchId !== searchIdRef.current) return;

          console.error('AI 다중 검색 오류:', error);
          consecutiveErrors += 1;

          if (consecutiveErrors < POLLING_MAX_CONSECUTIVE_ERRORS) {
            scheduleNextPoll();
            return;
          }

          setIsAnalyzing(false);
          setPollingNotice(
            '서버에 연결할 수 없어 분석 상태 갱신을 멈췄습니다. 잠시 후 다시 검색해 주세요.'
          );
        }
      };

      // 6. 최초 AI 검색 실행
      await pollSearchResults();
    } catch (error) {
      if (currentSearchId !== searchIdRef.current) return;

      console.error('실제 영상 검색 오류:', error);
      setSearchResults([]);
      setSelectedSegment(null);
      selectedSegmentRef.current = null;
      setIsLoading(false);
      setIsAnalyzing(false);
    }
  };

  // 최근 본 구간 저장
  const saveRecentSegment = (item: SearchResultItem) => {
    try {
      const recent = JSON.parse(
        localStorage.getItem('scenefinder-recent-segments') || '[]'
      ) as SearchResultItem[];

      // 같은 구간이 이미 있으면 기존 기록 제거
      const filtered = recent.filter(
        (recentItem) => recentItem.segment_id !== item.segment_id
      );

      // 가장 최근에 본 구간을 맨 앞으로
      const updated = [item, ...filtered].slice(0, 20);

      localStorage.setItem(
        'scenefinder-recent-segments',
        JSON.stringify(updated)
      );
    } catch (error) {
      console.error('최근 본 구간 저장 중 오류:', error);
    }
  };

  // 목록을 떠날 때 스크롤 위치 저장 후 맨 위로
  const leaveList = () => {
    if (listVisibleRef.current) {
      listScrollRef.current = window.scrollY;
    }

    window.scrollTo(0, 0);
  };

  // 플레이어 화면을 열 때: 뒤로가기로 목록에 돌아올 수 있도록 기록 추가
  const enterPlayer = () => {
    if (window.history.state?.sceneFinderView === 'player') return;

    leaveList();
    window.history.pushState({ sceneFinderView: 'player' }, '', '/search');
  };

  // 검색 목록으로 돌아가기 (저장한 스크롤 위치 복원)
  const returnToList = () => {
    selectedSegmentRef.current = null;
    setSelectedSegment(null);
    setPreviewVideoId(null);
    restoreListScrollRef.current = true;
  };

  // 플레이어 사이드바의 '검색' 버튼
  const handleBackToList = () => {
    if (window.history.state?.sceneFinderView === 'player') {
      window.history.back(); // popstate에서 returnToList 처리
    } else {
      returnToList();
    }
  };

  // 분석 로딩 화면의 '목록으로'
  const handleBackFromCardAnalysis = () => {
    cancelCardAnalysis();
    restoreListScrollRef.current = true;
  };

  // 검색 결과 클릭
  const handleSelectResult = (item: SearchResultItem) => {
    enterPlayer();
    selectedSegmentRef.current = item;
    setSelectedSegment(item);
    setPreviewVideoId(null);
    setCurrentVideoId(item.video_id);
    saveRecentSegment(item);
  };

  // 검색 목록의 영상 카드 클릭
  const handleSelectCard = (card: SearchCard) => {
    // 분석이 끝난 영상은 가장 관련 있는 구간부터 재생
    if (card.status === 'done' && card.segments.length > 0) {
      handleSelectResult(card.segments[0]);
      return;
    }

    // 분석 전/결과 없음/실패 영상은 분석 로딩 화면에서 이 영상만 따로 분석
    // (플레이어 오른쪽 목록에서 누른 경우: 플레이어 기록을 목록 상태로 바꿔
    //  분석 후 다시 플레이어를 열 때 뒤로가기 기록이 맞게 쌓이도록 함)
    if (window.history.state?.sceneFinderView === 'player') {
      window.history.replaceState(null, '', '/search');
    }

    leaveList();
    startCardAnalysis(card);
  };

  // 분석 로딩 화면: 이 영상의 분석을 바로 시작하고 상태를 polling
  // 완료 → 가장 관련 있는 구간부터 자동 재생, 실패 → 실패 안내 + 처음부터 재생 옵션
  const startCardAnalysis = (card: SearchCard) => {
    cancelCardAnalysis();

    const analysisId = cardAnalysisIdRef.current;
    const isCurrent = () => analysisId === cardAnalysisIdRef.current;
    const yid = card.youtubeVideoId;
    const query = activeQueryRef.current;
    const startedAt = Date.now();
    let consecutiveErrors = 0;

    selectedSegmentRef.current = null;
    setSelectedSegment(null);
    setPreviewVideoId(null);
    setCardAnalysis({
      card,
      phase: 'loading',
      status: card.status === 'queued' ? 'queued' : 'analyzing',
    });

    const updateCardStatus = (info: CardStatusInfo) =>
      setCardStatuses((previous) =>
        yid in previous ? { ...previous, [yid]: info } : previous
      );

    const fail = (message: string) => {
      if (!isCurrent()) return;

      setCardAnalysis({ card, phase: 'failed', status: 'queued', message });
      updateCardStatus({ status: 'failed' });
    };

    const scheduleNext = () => {
      cardAnalysisTimerRef.current = setTimeout(() => {
        cardAnalysisTimerRef.current = null;
        void pollStatus();
      }, POLLING_INTERVAL_MS);
    };

    // 분석이 끝난 영상의 검색 결과 반영
    const finish = (response: SingleSearchResponse) => {
      if (!isCurrent()) return;

      const { results, video } = convertSingleSearchResults(
        response,
        card.video
      );

      if (video) {
        setVideosMap((previous) => {
          const updated = { ...previous, [video.video_id]: video };

          localStorage.setItem(
            'scenefinder-video-metadata',
            JSON.stringify(updated)
          );

          return updated;
        });
      }

      if (!video || results.length === 0) {
        setCardAnalysis({ card, phase: 'no_results', status: 'queued' });
        updateCardStatus({ status: 'no_results', captionStatus: response.caption_status });
        return;
      }

      // 오른쪽 결과 목록에도 이 영상의 구간이 보이도록 합치기
      setSearchResults((previous) => [
        ...previous.filter((item) => item.video_id !== video.video_id),
        ...results,
      ]);
      updateCardStatus({ status: 'done', captionStatus: response.caption_status });

      setCardAnalysis(null);
      handleSelectResult(results[0]);
    };

    // 분석 시작/결과 조회 (이미 분석된 영상이면 바로 결과가 옴)
    const requestSearch = async () => {
      try {
        const response = await searchSingleVideo(yid, query, 5);

        if (!isCurrent()) return;

        if (response.status === 'INDEXED') {
          finish(response);
        } else {
          scheduleNext();
        }
      } catch (error) {
        console.error('개별 영상 분석 요청 오류:', error);
        fail(
          error instanceof Error
            ? error.message
            : '영상 분석을 시작하지 못했습니다.'
        );
      }
    };

    // 분석 상태 확인 (FAILED가 다시 분석되지 않도록 상태 조회 API 사용)
    const pollStatus = async () => {
      if (!isCurrent()) return;

      try {
        const status = await getYouTubeVideoStatus(yid);

        if (!isCurrent()) return;

        consecutiveErrors = 0;

        if (status.status === 'INDEXED') {
          await requestSearch();
          return;
        }

        if (status.status === 'FAILED') {
          fail(status.error_message || '영상 분석에 실패했습니다.');
          return;
        }

        if (Date.now() - startedAt > POLLING_MAX_DURATION_MS) {
          fail('분석이 너무 오래 걸리고 있습니다. 잠시 후 다시 시도해 주세요.');
          return;
        }

        setCardAnalysis((previous) =>
          previous && isCurrent()
            ? {
                ...previous,
                status:
                  status.status === 'PROCESSING' ? 'analyzing' : 'queued',
              }
            : previous
        );
        scheduleNext();
      } catch (error) {
        if (!isCurrent()) return;

        console.error('영상 분석 상태 확인 오류:', error);
        consecutiveErrors += 1;

        if (consecutiveErrors < POLLING_MAX_CONSECUTIVE_ERRORS) {
          scheduleNext();
        } else {
          fail('서버에 연결할 수 없어 분석 상태를 확인하지 못했습니다.');
        }
      }
    };

    void requestSearch();
  };

  // 분석 로딩 화면: 실패/결과 없음일 때 처음부터 재생
  const handlePlayCardFromStart = () => {
    if (!cardAnalysis) return;

    const yid = cardAnalysis.card.youtubeVideoId;

    enterPlayer();
    cancelCardAnalysis();
    selectedSegmentRef.current = null;
    setSelectedSegment(null);
    setPreviewVideoId(yid);
    setCurrentVideoId(yid);
  };

  // 라이브러리에 저장된 구간 다시 열기
  const handleOpenLibrarySegment = (item: SearchResultItem) => {
    stopPolling();

    selectedSegmentRef.current = item;
    setSelectedSegment(item);
    setPreviewVideoId(null);
    setCurrentVideoId(item.video_id);
    saveRecentSegment(item);

    // 검색 결과 영역에서도 현재 구간이 보이도록 설정
    setSearchResults([item]);
    setSearchVideoIds([]);
    setCardStatuses({});

    setCurrentView('player');

    if (
      typeof window !== 'undefined' &&
      window.location.pathname !== '/search'
    ) {
      window.history.pushState(null, '', '/search');
    }
  };

  // 홈으로 이동
  const handleNavigateHome = () => {
    stopPolling();
    setCurrentView('home');

    if (
      typeof window !== 'undefined' &&
      window.location.pathname !== '/'
    ) {
      window.history.pushState(null, '', '/');
    }
  };

  // 영상 탐색 화면으로 이동
  const handleNavigateBrowse = () => {
    stopPolling();
    setCurrentView('browse');

    if (
      typeof window !== 'undefined' &&
      window.location.pathname !== '/browse'
    ) {
      window.history.pushState(null, '', '/browse');
    }
  };

  // 로그인 화면으로 이동
  const handleNavigateAuth = () => {
    stopPolling();
    setCurrentView('auth');

    if (
      typeof window !== 'undefined' &&
      window.location.pathname !== '/login'
    ) {
      window.history.pushState(null, '', '/login');
    }
  };

  // 라이브러리 화면으로 이동
  const handleNavigateLibrary = () => {
    stopPolling();
    setCurrentView('library');

    if (
      typeof window !== 'undefined' &&
      window.location.pathname !== '/library'
    ) {
      window.history.pushState(null, '', '/library');
    }
  };

  // 로그인 성공
  const handleLoginSuccess = (loggedInUser: User) => {
    stopPolling();
    setUser(loggedInUser);
    setCurrentView('home');

    if (typeof window !== 'undefined') {
      window.history.pushState(null, '', '/');
    }
  };

  // 로그아웃
  const handleLogout = () => {
    stopPolling();
    localStorage.removeItem('scenefinder-user');
    // 로그아웃 후에도 토큰이 남아 검색 기록/즐겨찾기 요청에 붙는 것을 방지
    localStorage.removeItem('scenefinder-access-token');
    localStorage.removeItem('scenefinder-refresh-token');
    setUser(null);
    setCurrentView('home');

    if (typeof window !== 'undefined') {
      window.history.pushState(null, '', '/');
    }
  };

// 현재 사용자가 선택한 실제 영상
const activeVideo = videosMap[currentVideoId];

  // 검색 목록 카드 (완료 영상은 관련도 순, 나머지는 YouTube 순서)
  const searchCards = useMemo(
    () =>
      buildSearchCards(searchVideoIds, cardStatuses, searchResults, videosMap),
    [searchVideoIds, cardStatuses, searchResults, videosMap]
  );

  const isPlayerOpen =
    (selectedSegment !== null || previewVideoId !== null) &&
    activeVideo !== undefined;

  const isListVisible =
    currentView === 'player' && !isPlayerOpen && cardAnalysis === null;

  // 목록으로 돌아왔을 때 저장해 둔 스크롤 위치 복원 (그리기 전에 적용)
  useLayoutEffect(() => {
    listVisibleRef.current = isListVisible;

    if (isListVisible && restoreListScrollRef.current) {
      restoreListScrollRef.current = false;
      window.scrollTo(0, listScrollRef.current);
    }
  }, [isListVisible]);

  // 현재 영상의 모든 AI 구간 (플레이어 아래 타임라인/구간 목록)
  // 라이브러리에서 연 경우처럼 카드가 없으면 받은 결과 중 같은 영상 구간 사용
  const currentCard = activeVideo?.youtube_video_id
    ? searchCards.find(
        (card) => card.youtubeVideoId === activeVideo.youtube_video_id
      )
    : undefined;
  const currentSegments =
    currentCard?.segments ??
    searchResults.filter((item) => item.video_id === activeVideo?.video_id);

  return (
    <div className="min-h-screen bg-[#F8FAFC] text-slate-900 flex flex-col font-sans">
      <Header
        currentView={currentView}
        searchQuery={searchQuery}
        onSearchQueryChange={(val) => setSearchQuery(val)}
        onSearchSubmit={() => executeSearch(searchQuery)}
        onNavigateHome={handleNavigateHome}
        onNavigateBrowse={handleNavigateBrowse}
        onNavigateAuth={handleNavigateAuth}
        onNavigateLibrary={handleNavigateLibrary}
        onLogout={handleLogout}
        user={user}
      />

      {currentView === 'home' && (
        <HomeView
          initialQuery={searchQuery}
          onSearch={(query, targetVideoId) =>
            executeSearch(query, targetVideoId)
          }
        />
      )}

      {currentView === 'browse' && (
        <BrowseView
          onSearch={(query, targetVideoId) =>
            executeSearch(query, targetVideoId)
          }
        />
      )}

      {currentView === 'player' && (
        !isPlayerOpen ? (
          <VideoSearchListView
            cards={searchCards}
            isLoading={isLoading}
            isAnalyzing={isAnalyzing}
            pollingNotice={pollingNotice}
            searchQuery={searchQuery}
            onSelectCard={handleSelectCard}
            cardAnalysis={cardAnalysis}
            onPlayCardFromStart={handlePlayCardFromStart}
            onCancelCardAnalysis={handleBackFromCardAnalysis}
          />
        ) : (
          <PlayerView
            currentVideo={activeVideo}
            selectedSegment={selectedSegment}
            currentSegments={currentSegments}
            onSelectSegment={handleSelectResult}
            cards={searchCards}
            onSelectCard={handleSelectCard}
            onBackToList={handleBackToList}
            isLoading={isLoading || isAnalyzing}
            searchQuery={searchQuery}
            onNavigateHome={handleNavigateHome}
            onSelectSuggestion={(rec) => executeSearch(rec)}
          />
        )
      )}

      {currentView === 'auth' && (
        <AuthView
          onNavigateHome={handleNavigateHome}
          onLoginSuccess={handleLoginSuccess}
        />
      )}

      {currentView === 'library' && (
        <LibraryView
          onOpenSegment={handleOpenLibrarySegment}
          videosMap={videosMap}
        />
      )}
    </div>
  );
}