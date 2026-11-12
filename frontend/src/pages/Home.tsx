import { useState, type FormEvent } from 'react';
import '../styles/home.css';
import { Icon, type IconName } from '../components/Icon';
import { SceneRow, SourceTag, Thumb } from '../components/Common';
import { audienceGroups, popularScenes } from '../data/mock';
import { go } from '../router';

const EXAMPLES = ['기초연금 신청 방법 알려줘', '월세 지원 받을 수 있어?', '아이 돌봄 신청하는 법', '틀니 지원 있어?'];

export default function Home() {
  const [q, setQ] = useState('');
  const [tab, setTab] = useState(0);

  const search = (text: string) => go(`/results?q=${encodeURIComponent(text || '기초연금 신청서 어떻게 써요?')}`);
  const onSubmit = (e: FormEvent) => { e.preventDefault(); search(q); };

  return (
    <main className="page-home">
      <section className="hero"><div className="wrap">
        <span className="lbl"><i />공식 정책정보 · 안내 영상 장면 검색</span>
        <h1>나에게 필요한 복지혜택,<br /><em>영상 속 신청 장면</em>까지 한 번에 바로봄</h1>
        <p className="sub">궁금한 것을 물어보면, 공식 정책정보와 안내 영상 속 필요한 장면을 함께 찾아드려요.</p>
        <form className="sbox" role="search" onSubmit={onSubmit}>
          <div className="row">
            <label className="in">
              <span className="sr-only">검색어</span>
              <Icon name="search" />
              <input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="예: 기초연금 신청서 어떻게 써요?" />
              <button type="button" className="mic"><Icon name="mic" />말로 묻기</button>
            </label>
            <button className="btn btn-pri go" type="submit">검색</button>
          </div>
          <p className="help"><Icon name="info" />정책 이름을 몰라도 괜찮아요. 평소 말하듯 물어보세요.</p>
        </form>
        <div className="ex">
          <span>이렇게 물어보세요</span>
          {EXAMPLES.map((t) => (
            <button key={t} className="chip" onClick={() => search(t)}>{t}</button>
          ))}
        </div>
      </div></section>

      <div className="wrap">
        <section className="how">
          <div className="intro">
            <div className="eyebrow">이렇게 찾아드려요</div>
            <h2>긴 영상을 처음부터<br />볼 필요 없어요</h2>
            <p>질문에 맞는 장면을 찾아 그 시점부터 재생해요.</p>
          </div>
          {([
            { n: 1, icon: 'db', title: '공식 정책정보 확인', desc: '지원 대상·금액·기간을 공공데이터로 보여드려요.' },
            { n: 2, icon: 'scan', title: '영상 속 장면 바로 보기', desc: 'AI가 찾은 장면부터 바로 재생해요.' },
            { n: 3, icon: 'ext', title: '공식 신청 페이지로', desc: '복지로·정부24 신청 화면으로 이동해요.' },
          ] as { n: number; icon: IconName; title: string; desc: string }[]).map((s) => (
            <div key={s.n} className="card st">
              <div className="n"><b>{s.n}</b><Icon name={s.icon} /></div>
              <h3>{s.title}</h3>
              <p>{s.desc}</p>
            </div>
          ))}
        </section>

        <section className="section">
          <div className="sec-h"><div><h2>누구의 복지혜택을 찾으세요?</h2><p>대상을 고르면 관련 정책과 영상 장면을 모아 보여드려요.</p></div></div>
          <div className="tabs3" role="tablist" aria-label="찾는 방법">
            {audienceGroups.map((g, i) => (
              <button key={g.label} role="tab" aria-selected={tab === i} onClick={() => setTab(i)}>{g.label}</button>
            ))}
          </div>
          <div className="who">
            {audienceGroups[tab].items.map((it) => (
              <a key={it.title} className="card" href={`#/results?q=${encodeURIComponent(it.policies[0])}`}>
                <div className="top"><span className="ic"><Icon name={it.icon as IconName} /></span><span className="tag tag-gray">{it.tag}</span></div>
                <h3>{it.title}</h3>
                <div className="tags">{it.policies.map((p) => <span key={p}>{p}</span>)}</div>
                <span className="go">정책 보기<Icon name="arrow" /></span>
              </a>
            ))}
          </div>
        </section>

        <section className="section">
          <div className="sec-h">
            <div><h2>많이 찾는 신청 장면</h2><p>시간을 누르면 그 장면부터 바로 재생돼요.</p></div>
            <a className="btn btn-line" href="#/results">전체 보기</a>
          </div>
          <div className="pop">
            {popularScenes.map((c) => (
              <article key={c.title} className="card">
                <Thumb href="#/watch/v1" type={c.thumbType} duration={c.duration} />
                <div className="bd">
                  <div className="meta"><span className="tag tag-blue">{c.policy}</span>[게시기관]</div>
                  <h3>{c.title}</h3>
                  <span className="lab">AI가 찾은 장면</span>
                  <div className="scenes">
                    {c.scenes.map((s) => <SceneRow key={s.t} href={`#/watch/v1?t=${s.t}`} t={s.t} label={s.label} hit={'hit' in s && s.hit} />)}
                  </div>
                  <a className="btn btn-soft btn-block cta" href="#/watch/v1">장면 바로 보기</a>
                </div>
              </article>
            ))}
          </div>
        </section>

        <div className="trust">
          <SourceTag kind="gov" /><SourceTag kind="ai" />
          두 정보를 나눠서 보여드리고, 다르면 공식 정보를 먼저 안내해요.
          <a href="#/guide">이용 안내 보기<Icon name="arrow" /></a>
        </div>
      </div>
    </main>
  );
}
