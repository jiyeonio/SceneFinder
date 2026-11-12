import type { Verification } from '../data/types';
import { fmt } from '../utils';
import { Icon } from './Icon';

/** 영상 썸네일 — 실제 영상 캡처(thumbnailUrl)가 있으면 그걸 보여주고, 없으면 화면 모양으로 표시 */
export function Thumb({ href, type = 'screen', duration, src }: {
  href: string; type?: 'screen' | 'paper' | 'phone'; duration: string; src?: string;
}) {
  return (
    <a className={`thumb ${type === 'screen' ? '' : type}`} href={href}>
      {src ? (
        <img src={src} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
      ) : (
        <span className="scr"><i className="t" /><i /><i className="hl" /><i /></span>
      )}
      <span className="play"><Icon name="play" fill /></span>
      <span className="at">{duration}</span>
    </a>
  );
}

/** 검증 상태 배지 — 색 + 아이콘 + 글자로 구분 */
export function VerifyBadge({ v, long }: { v: Verification; long?: boolean }) {
  if (v === 'screen') return <span className="vb vb-screen"><Icon name="check" />실제 화면</span>;
  if (v === 'subtitle') return <span className="vb vb-sub"><Icon name="text" />{long ? '자막만 · 화면 없음' : '자막만'}</span>;
  return <span className="vb vb-none">{long ? '해당 장면 없음' : '신청 단계 아님'}</span>;
}

/** 정보 출처 라벨 */
export function SourceTag({ kind }: { kind: 'gov' | 'ai' }) {
  return kind === 'gov'
    ? <span className="src src-gov"><Icon name="db" />공식 정책정보</span>
    : <span className="src src-ai"><Icon name="scan" />AI 영상 분석</span>;
}

/** 장면 행 (시간 + 이름) — 누르면 그 시간부터 재생 */
export function SceneRow({ href, t, label, hit }: { href: string; t: number; label: string; hit?: boolean }) {
  return (
    <a className={`scene${hit ? ' hit' : ''}`} href={href}>
      <span className="pl"><Icon name="play" fill /></span>
      <span className="t num">{fmt(t)}</span>
      <span className="l">{label}</span>
    </a>
  );
}
