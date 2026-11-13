import { useState, type FormEvent } from 'react';
import '../styles/home.css';
import { Icon, type IconName } from '../components/Icon';
import { go } from '../router';
import { fmt } from '../utils';
import { popularScenes } from '../data/mock';

const CATEGORIES = ['전체', '어르신', '장애인', '가족·육아', '청년', '저소득'];

const QUICK: { icon: IconName; label: string; q: string }[] = [
  { icon: 'coin', label: '기초연금', q: '기초연금 신청 방법' },
  { icon: 'care', label: '장기요양', q: '노인장기요양보험 신청' },
  { icon: 'brief', label: '노인일자리', q: '노인일자리 신청' },
  { icon: 'brain', label: '치매 지원', q: '치매안심센터' },
  { icon: 'bolt', label: '에너지바우처', q: '에너지바우처 신청' },
  { icon: 'heart', label: '아이돌봄', q: '아이돌봄 신청' },
  { icon: 'house', label: '청년 월세', q: '청년월세 지원' },
  { icon: 'wheel', label: '장애인연금', q: '장애인연금 신청' },
];

// 시연 영상 세트 (data/mock.ts popularScenes — 실제 영상 ID와 시연 질문으로 시험한 장면 시간)
const AUDIENCE: Record<string, number> = { 기초연금: 1, '청년월세 지원': 2, 아이돌봄서비스: 2 };
const TABS = ['전체', '어르신', '청년·가족'];
const RECENT = popularScenes.flatMap((c) => c.scenes.filter((x) => 'hit' in x && x.hit).map((x) => ({
  tab: AUDIENCE[c.policy] ?? 0, title: `${c.policy.replace(' 지원', '').replace('서비스', '')} ${x.label}`, href: `#/watch/${c.videoId}?t=${x.t}`, t: x.t,
})));

const HELP: { icon: IconName; label: string; href: string }[] = [
  { icon: 'phone', label: '129 상담', href: 'tel:129' },
  { icon: 'pin', label: '주민센터', href: '#' },
  { icon: 'info', label: '이용 안내', href: '#/guide' },
  { icon: 'text', label: '손말이음', href: 'tel:107' },
];

// 시연 질문 (팀이 백엔드로 시험한 질문) + 그 질문의 대표 영상 장면
const ICON_OF: Record<string, IconName> = { 기초연금: 'coin', '청년월세 지원': 'house', 아이돌봄서비스: 'heart' };
const ASKS = ['기초연금 신청할 때\n뭐 챙겨가야 돼요?', '기초연금\n신청하는 법', '월세 지원 받으려면\n뭐 내야 돼요?', '아이돌봄\n어디서 신청해요?'];
const CARDS = popularScenes.slice(0, 4).map((c, i) => ({
  cat: c.policy.replace(' 지원', '').replace('서비스', ''), icon: ICON_OF[c.policy] ?? 'play', q: ASKS[i], videoId: c.videoId,
  links: c.scenes.map((x) => ({ t: x.t, label: x.label })),
}));

export default function Home() {
  const [q, setQ] = useState('');
  const [cat, setCat] = useState('전체');
  const [tab, setTab] = useState(0);

  const search = (text: string) => go(`/results?q=${encodeURIComponent(text || '기초연금 신청서 어떻게 써요?')}`);
  const onSubmit = (e: FormEvent) => { e.preventDefault(); search(q); };
  const list = RECENT.filter((r) => tab === 0 || r.tab === tab);

  return (
    <main className="page-home np">
      <section className="np-hero"><div className="wrap">
        <div className="np-copy">
          <p className="ey">복지 안내 영상, 필요한 장면만</p>
          <h1>신청 장면까지<br />바로 보여드려요</h1>
          <a className="lk" href="#/guide">이용 안내 보기 &gt;&gt;</a>
        </div>
        <div className="np-vis" aria-hidden="true">
          <div className="fr">
            <div className="scr"><i className="t" /><i /><i className="hl" /><i /></div>
            <div className="tl"><span className="seg" /><span className="hd" /></div>
          </div>
          <div className="pin"><Icon name="play" fill />01:54 신청 서류 보기</div>
        </div>
        <div className="np-cards">
          <section className="np-box">
            <div className="hd"><h2>많이 찾는 신청 장면</h2><a className="more" href="#/results">더보기<Icon name="plus" /></a></div>
            <div className="tb" role="tablist">
              {TABS.map((t, i) => <button key={t} role="tab" aria-selected={tab === i} onClick={() => setTab(i)}>{t}</button>)}
            </div>
            <ul>
              {list.slice(0, 3).map((r) => (
                <li key={r.href}><a href={r.href}><span>{r.title}</span><em className="num"><Icon name="play" fill />{fmt(r.t)}</em></a></li>
              ))}
            </ul>
          </section>
          <section className="np-box">
            <div className="hd"><h2>혼자 하기 어려우세요?</h2></div>
            <div className="help">
              {HELP.map((h) => <a key={h.label} href={h.href}><span className="ic"><Icon name={h.icon} /></span>{h.label}</a>)}
            </div>
          </section>
        </div>
      </div></section>

      <div className="wrap np-float">
        <div className="pills"><span className="on">자주 찾는 복지</span></div>
        <nav className="bar" aria-label="자주 찾는 복지">
          {QUICK.map((it) => (
            <button key={it.label} onClick={() => search(it.q)}><Icon name={it.icon} /><span>{it.label}</span></button>
          ))}
        </nav>
      </div>

      <section className="np-ask"><div className="wrap">
        <h2>어떤 도움이 필요하세요?</h2>
        <form className="pill" role="search" onSubmit={onSubmit}>
          <label className="sel">
            <span className="sr-only">분류</span>
            <select value={cat} onChange={(e) => setCat(e.target.value)}>
              {CATEGORIES.map((c) => <option key={c}>{c}</option>)}
            </select>
            <Icon name="chev" />
          </label>
          <input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="말하듯 물어보세요. 예: 기초연금 신청서 어떻게 써요?" aria-label="검색어" />
          <button type="button" className="mic" aria-label="말로 묻기"><Icon name="mic" /></button>
          <button type="submit" className="go" aria-label="검색"><Icon name="search" /></button>
        </form>
      </div></section>

      <section className="wrap np-menu">
        <div className="intro">
          <h2>이렇게<br />찾아요</h2>
          <ol>
            <li><b>1</b>말하듯 물어보기</li>
            <li><b>2</b>찾은 장면 보기</li>
            <li><b>3</b>복지로에서 신청</li>
          </ol>
        </div>
        <div className="row">
          {CARDS.map((c) => (
            <article key={c.videoId} className="mc">
              <div className="top"><small>{c.cat}</small><span className="ic"><Icon name={c.icon} /></span></div>
              <h3><a className="qa" href={`#/results?q=${encodeURIComponent(c.q.replace('\n', ' '))}`}>{c.q.split('\n').map((l, i) => <span key={i}>{l}<br /></span>)}</a></h3>
              {c.links.map((l) => (
                <a key={l.label} href={`#/watch/${c.videoId}?t=${l.t}`}><span><em className="num">{fmt(l.t)}</em>{l.label}</span><Icon name="arrow" /></a>
              ))}
            </article>
          ))}
        </div>
      </section>

      <section className="wrap np-promo">
        <a className="pm p1" href="#/guide"><b>처음 오셨나요?</b><i className="btn-s">이용 안내</i></a>
        <a className="pm p2" href="#/guide"><b>자주 묻는 질문</b><i className="btn-s">바로가기</i></a>
        <div className="pm p3"><b>편하게 보기</b>
          <div className="mini"><span><b>가</b>큰 글씨</span><span><Icon name="contrast" />고대비</span><span><Icon name="speaker" />읽어주기</span><span><Icon name="text" />큰 자막</span></div>
        </div>
        <a className="pm p4" href="tel:129"><small>보건복지상담센터</small><b className="big">국번 없이 129</b></a>
      </section>
    </main>
  );
}
