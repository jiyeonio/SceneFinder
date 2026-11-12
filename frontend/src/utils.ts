/** 초 → "08:35" */
export function fmt(sec: number): string {
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

/** 349700 → "349,700" */
export function won(n: number): string {
  return n.toLocaleString('ko-KR');
}

/** 타임라인 위치(%) */
export function pct(sec: number, total: number): string {
  return `${((sec / total) * 100).toFixed(2)}%`;
}
