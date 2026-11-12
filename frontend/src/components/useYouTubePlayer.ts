// YouTube IFrame 플레이어 훅 — main의 VideoPlayer.tsx에서 IFrame API 부분만 옮김.
// 화면(컨트롤·타임라인)은 Watch.tsx 디자인을 그대로 쓰고, 이 훅은 재생·이동·속도·현재 시간만 다룬다.
import { useCallback, useEffect, useRef, useState } from 'react';

interface YTPlayer {
  playVideo: () => void;
  pauseVideo: () => void;
  seekTo: (seconds: number, allowSeekAhead: boolean) => void;
  getCurrentTime: () => number;
  getDuration: () => number;
  getPlayerState: () => number;
  setPlaybackRate: (rate: number) => void;
  destroy: () => void;
}
interface YTApi {
  Player: new (el: HTMLElement, opts: {
    videoId: string; width?: string | number; height?: string | number; playerVars?: Record<string, number>;
    events?: { onReady?: () => void; onStateChange?: (e: { data: number }) => void; onError?: (e: { data: number }) => void };
  }) => YTPlayer;
}
declare global {
  interface Window { YT?: YTApi; onYouTubeIframeAPIReady?: () => void }
}

let apiPromise: Promise<YTApi> | null = null;
function loadApi(): Promise<YTApi> {
  if (window.YT?.Player) return Promise.resolve(window.YT);
  if (apiPromise) return apiPromise;
  apiPromise = new Promise((resolve, reject) => {
    const prev = window.onYouTubeIframeAPIReady;
    window.onYouTubeIframeAPIReady = () => {
      prev?.();
      if (window.YT?.Player) resolve(window.YT); else reject(new Error('YouTube API를 불러오지 못했어요'));
    };
    if (!document.querySelector('script[src="https://www.youtube.com/iframe_api"]')) {
      const s = document.createElement('script');
      s.src = 'https://www.youtube.com/iframe_api';
      s.async = true;
      s.onerror = () => { apiPromise = null; reject(new Error('YouTube API 스크립트를 불러오지 못했어요')); };
      document.head.appendChild(s);
    }
  });
  return apiPromise;
}

/** mountRef 안에 플레이어를 만들고, 0.25초마다 현재 시간을 알려 줌 */
export function useYouTubePlayer(youtubeId: string | undefined, startAt: number) {
  const mountRef = useRef<HTMLDivElement | null>(null);
  const playerRef = useRef<YTPlayer | null>(null);
  const startRef = useRef(startAt);
  const [time, setTime] = useState(startAt);
  const [playing, setPlaying] = useState(false);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => { startRef.current = startAt; }, [startAt]);

  useEffect(() => {
    const host = mountRef.current;
    if (!youtubeId || !host) return;
    let cancelled = false;
    let timer = 0;
    let created: YTPlayer | null = null;
    setReady(false); setError('');
    loadApi().then((YT) => {
      if (cancelled || !host.isConnected) return;
      const el = document.createElement('div');
      host.appendChild(el);
      created = new YT.Player(el, {
        videoId: youtubeId, width: '100%', height: '100%',
        playerVars: { autoplay: 0, controls: 0, playsinline: 1, rel: 0, modestbranding: 1, cc_load_policy: 0, iv_load_policy: 3 },
        events: {
          onReady: () => {
            if (cancelled || !created) return;
            playerRef.current = created;
            created.seekTo(startRef.current, true);
            created.playVideo();
            setReady(true);
            timer = window.setInterval(() => {
              try {
                const t = created!.getCurrentTime();
                if (Number.isFinite(t)) setTime(t);
                setPlaying(created!.getPlayerState() === 1);
              } catch { /* 종료 중 */ }
            }, 250);
          },
          onError: () => { if (!cancelled) setError('이 영상은 여기서 재생할 수 없어요. YouTube에서 직접 열어 주세요.'); },
        },
      });
    }).catch((e: Error) => { if (!cancelled) setError(e.message); });
    return () => {
      cancelled = true; window.clearInterval(timer);
      try { created?.destroy(); } catch { /* 무시 */ }
      playerRef.current = null;
      host.innerHTML = '';
    };
  }, [youtubeId]);

  const seek = useCallback((t: number, play = true) => {
    const p = playerRef.current;
    setTime(t);
    if (!p) { startRef.current = t; return; }
    p.seekTo(Math.max(0, t), true);
    if (play) p.playVideo();
  }, []);
  const toggle = useCallback(() => {
    const p = playerRef.current; if (!p) return;
    if (p.getPlayerState() === 1) p.pauseVideo(); else p.playVideo();
  }, []);
  const setRate = useCallback((r: number) => { playerRef.current?.setPlaybackRate(r); }, []);

  return { mountRef, time, playing, ready, error, seek, toggle, setRate };
}
