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

/** 공공데이터 문의처 「보건복지상담센터/129 · 국민연금공단 콜센터/1355」 → [{name, tel}] (원문 그대로 나눔, 번호 없는 항목은 이름만) */
export function contacts(raw?: string | null): { name: string; tel: string }[] {
  return (raw ?? '').split(/\s*·\s*|\|\|/).map((x) => x.trim()).filter(Boolean).map((x) => {
    const m = x.match(/^(.*?)[\s/]*((?:\d{2,4}-)?\d{3,4}-?\d{4}|\d{3,4})$/);
    return m ? { name: m[1].replace(/\/$/, '').trim(), tel: m[2] } : { name: x, tel: '' };
  });
}
