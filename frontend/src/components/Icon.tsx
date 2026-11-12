import type { CSSProperties } from 'react';

/** 앱 전체에서 한 번만 렌더하는 아이콘 묶음 */
export function IconSprite() {
  return (
    <svg width="0" height="0" style={{ position: 'absolute' }} aria-hidden="true">
      <symbol id="i-search" viewBox="0 0 24 24"><circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" /></symbol>
      <symbol id="i-mic" viewBox="0 0 24 24"><rect x="9" y="3" width="6" height="11" rx="3" /><path d="M5 11a7 7 0 0 0 14 0" /><path d="M12 18v3" /></symbol>
      <symbol id="i-phone" viewBox="0 0 24 24"><path d="M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.5 19.5 0 0 1-6-6A19.8 19.8 0 0 1 2.1 4.2 2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1.9.4 1.8.7 2.7a2 2 0 0 1-.5 2.1L8 9.8a16 16 0 0 0 6 6l1.3-1.3a2 2 0 0 1 2.1-.4c.9.3 1.8.6 2.7.7a2 2 0 0 1 1.7 2z" /></symbol>
      <symbol id="i-play" viewBox="0 0 24 24"><path d="M8 5.5v13a1 1 0 0 0 1.5.86l10.5-6.5a1 1 0 0 0 0-1.72L9.5 4.64A1 1 0 0 0 8 5.5z" /></symbol>
      <symbol id="i-pause" viewBox="0 0 24 24"><path d="M8 5v14M16 5v14" /></symbol>
      <symbol id="i-check" viewBox="0 0 24 24"><path d="m5 12 5 5 9-10" /></symbol>
      <symbol id="i-arrow" viewBox="0 0 24 24"><path d="M5 12h14" /><path d="m13 6 6 6-6 6" /></symbol>
      <symbol id="i-back" viewBox="0 0 24 24"><path d="M19 12H5" /><path d="m11 6-6 6 6 6" /></symbol>
      <symbol id="i-ext" viewBox="0 0 24 24"><path d="M14 4h6v6" /><path d="M20 4 11 13" /><path d="M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5" /></symbol>
      <symbol id="i-speaker" viewBox="0 0 24 24"><path d="M11 5 6 9H3v6h3l5 4z" /><path d="M15.5 8.5a5 5 0 0 1 0 7" /><path d="M18.5 5.5a9 9 0 0 1 0 13" /></symbol>
      <symbol id="i-alert" viewBox="0 0 24 24"><path d="M12 3 2 20h20z" /><path d="M12 10v4" /><path d="M12 17h.01" /></symbol>
      <symbol id="i-info" viewBox="0 0 24 24"><circle cx="12" cy="12" r="9" /><path d="M12 11v5" /><path d="M12 8h.01" /></symbol>
      <symbol id="i-contrast" viewBox="0 0 24 24"><circle cx="12" cy="12" r="9" /><path d="M12 3v18" /><path d="M12 3a9 9 0 0 1 0 18z" fill="currentColor" /></symbol>
      <symbol id="i-rew" viewBox="0 0 24 24"><path d="M3 12a9 9 0 1 0 3-6.7L3 8" /><path d="M3 3v5h5" /></symbol>
      <symbol id="i-full" viewBox="0 0 24 24"><path d="M4 9V4h5" /><path d="M20 9V4h-5" /><path d="M4 15v5h5" /><path d="M20 15v5h-5" /></symbol>
      <symbol id="i-pin" viewBox="0 0 24 24"><path d="M12 21s-7-6.1-7-11.5A7 7 0 0 1 19 9.5C19 14.9 12 21 12 21z" /><circle cx="12" cy="9.5" r="2.5" /></symbol>
      <symbol id="i-print" viewBox="0 0 24 24"><path d="M6 9V3h12v6" /><rect x="3" y="9" width="18" height="8" rx="2" /><path d="M7 14h10v7H7z" /></symbol>
      <symbol id="i-elder" viewBox="0 0 24 24"><circle cx="12" cy="4.5" r="2" /><path d="M12 7v6l-3 7" /><path d="m12 13 3 7" /><path d="M8 10h7" /><path d="M17 10v10" /></symbol>
      <symbol id="i-family" viewBox="0 0 24 24"><circle cx="9" cy="6" r="3" /><path d="M4 21v-2a5 5 0 0 1 10 0v2" /><circle cx="17.5" cy="10.5" r="2" /><path d="M15 21v-1.5a3 3 0 0 1 6 0V21" /></symbol>
      <symbol id="i-cap" viewBox="0 0 24 24"><path d="m2 9 10-5 10 5-10 5z" /><path d="M6 11v5c2 2 10 2 12 0v-5" /></symbol>
      <symbol id="i-wheel" viewBox="0 0 24 24"><circle cx="12" cy="4.5" r="2" /><path d="M11 8v5h5l2 6" /><path d="M8 11.5A5.5 5.5 0 1 0 15 19" /></symbol>
      <symbol id="i-logo" viewBox="0 0 24 24"><rect x="3" y="5" width="18" height="14" rx="2.5" /><path d="M10.5 9.5v5l4-2.5z" fill="currentColor" /></symbol>
      <symbol id="i-repeat" viewBox="0 0 24 24"><path d="M17 2l3 3-3 3" /><path d="M4 11V9a4 4 0 0 1 4-4h12" /><path d="M7 22l-3-3 3-3" /><path d="M20 13v2a4 4 0 0 1-4 4H4" /></symbol>
      <symbol id="i-text" viewBox="0 0 24 24"><path d="M4 6h16M4 12h10M4 18h7" /></symbol>
      <symbol id="i-chev" viewBox="0 0 24 24"><path d="m6 9 6 6 6-6" /></symbol>
      <symbol id="i-bookmark" viewBox="0 0 24 24"><path d="M6 3h12v18l-6-4-6 4z" /></symbol>
      <symbol id="i-share" viewBox="0 0 24 24"><circle cx="18" cy="5" r="2.5" /><circle cx="6" cy="12" r="2.5" /><circle cx="18" cy="19" r="2.5" /><path d="m8.2 10.8 7.6-4.4M8.2 13.2l7.6 4.4" /></symbol>
      <symbol id="i-db" viewBox="0 0 24 24"><ellipse cx="12" cy="5" rx="8" ry="3" /><path d="M4 5v14c0 1.7 3.6 3 8 3s8-1.3 8-3V5" /><path d="M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3" /></symbol>
      <symbol id="i-scan" viewBox="0 0 24 24"><path d="M3 7V4h3M21 7V4h-3M3 17v3h3M21 17v3h-3" /><rect x="7" y="8" width="10" height="8" rx="1" /></symbol>
    </svg>
  );
}

export type IconName =
  | 'search' | 'mic' | 'phone' | 'play' | 'pause' | 'check' | 'arrow' | 'back' | 'ext' | 'speaker'
  | 'alert' | 'info' | 'contrast' | 'rew' | 'full' | 'pin' | 'print' | 'elder' | 'family' | 'cap'
  | 'wheel' | 'logo' | 'repeat' | 'text' | 'chev' | 'bookmark' | 'share' | 'db' | 'scan';

/** 아이콘. fill=true 면 채운 모양(재생 버튼 등) */
export function Icon({ name, fill, style }: { name: IconName; fill?: boolean; style?: CSSProperties }) {
  return (
    <svg className={fill ? 'i f' : 'i'} style={style} aria-hidden="true">
      <use href={`#i-${name}`} />
    </svg>
  );
}
