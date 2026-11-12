import { useEffect, useState, type ReactNode } from 'react';
import { Icon } from './Icon';

type FontSize = '1' | '2' | '3';

function load(key: string): string | null {
  try { return localStorage.getItem(key); } catch { return null; }
}
function save(key: string, value: string) {
  try { localStorage.setItem(key, value); } catch { /* 저장 못 해도 동작에는 문제 없음 */ }
}

/** 글자 크기 · 고대비 상태 (html 태그의 data-fs / data-contrast 로 전체 화면에 적용) */
export function useA11y() {
  const [fs, setFs] = useState<FontSize>(() => (load('bb-fs') as FontSize) || '1');
  const [contrast, setContrast] = useState<boolean>(() => load('bb-contrast') === '1');

  useEffect(() => {
    document.documentElement.setAttribute('data-fs', fs);
    save('bb-fs', fs);
  }, [fs]);
  useEffect(() => {
    if (contrast) document.documentElement.setAttribute('data-contrast', 'high');
    else document.documentElement.removeAttribute('data-contrast');
    save('bb-contrast', contrast ? '1' : '0');
  }, [contrast]);

  return { fs, setFs, contrast, setContrast };
}

function A11yBar() {
  const { fs, setFs, contrast, setContrast } = useA11y();
  const [reading, setReading] = useState(false);
  const sizes: { v: FontSize; label: string }[] = [
    { v: '1', label: '보통' }, { v: '2', label: '크게' }, { v: '3', label: '아주 크게' },
  ];
  return (
    <div className="a11y"><div className="wrap">
      <span className="lb">글자 크기</span>
      <div className="seg" role="group" aria-label="글자 크기">
        {sizes.map((s) => (
          <button key={s.v} className="fs-btn" data-v={s.v} aria-pressed={fs === s.v} onClick={() => setFs(s.v)}>
            <b>가</b>{s.label}
          </button>
        ))}
      </div>
      <button className="tog" aria-pressed={contrast} onClick={() => setContrast(!contrast)}><Icon name="contrast" />고대비</button>
      <button className="tog" aria-pressed={reading} onClick={() => setReading(!reading)}><Icon name="speaker" />화면 읽어주기</button>
      <span className="sp" />
      <span className="links">
        <a href="https://www.bokjiro.go.kr" target="_blank" rel="noreferrer">복지로 <Icon name="ext" /></a>
        <a href="https://www.gov.kr" target="_blank" rel="noreferrer">정부24 <Icon name="ext" /></a>
      </span>
    </div></div>
  );
}

const NAV = [
  { to: '/', label: '홈' },
  { to: '/results', label: '정책 찾기' },
  { to: '/watch', label: '영상 장면 찾기' },
  { to: '/guide', label: '이용 안내' },
];

function Header({ current }: { current: string }) {
  return (
    <header className="hdr"><div className="wrap">
      <a className="logo" href="#/">
        <span className="mk"><Icon name="logo" /></span>
        <span><b>복지바로봄</b><small>공모전 시제품</small></span>
      </a>
      <nav className="nav" aria-label="주요 메뉴">
        {NAV.map((n) => (
          <a key={n.to} href={`#${n.to}`} aria-current={current === n.to ? 'page' : undefined}>{n.label}</a>
        ))}
      </nav>
      <div className="end">
        <a className="btn btn-line" href="tel:129"><Icon name="phone" />상담 129</a>
        <a className="btn btn-dark" href="#/">로그인</a>
      </div>
    </div></header>
  );
}

function Footer() {
  return (
    <footer className="ft"><div className="wrap">
      <div>
        <a className="logo" href="#/"><span className="mk"><Icon name="logo" /></span><b>복지바로봄</b></a>
        <p>공공데이터포털 사회보장 Open API와 공개된 안내 영상을 연결한 공모전 시제품이에요. 정부 공식 서비스가 아니며, 신청은 복지로·정부24·주민센터에서 이뤄져요.</p>
        <p>화면의 금액·날짜·영상 시간은 시연용 예시예요. · 혜택발굴단 · 2026 사회보장 데이터 활용 AI 혁신 아이디어 경진대회</p>
      </div>
      <div className="calls">
        <span>보건복지상담센터<b>국번 없이 129</b></span>
        <span>국민연금공단<b>1355</b></span>
        <span>손말이음센터(청각·언어)<b>107</b></span>
      </div>
    </div></footer>
  );
}

export function Layout({ current, children }: { current: string; children: ReactNode }) {
  return (
    <>
      <A11yBar />
      <Header current={current} />
      {children}
      <Footer />
    </>
  );
}
