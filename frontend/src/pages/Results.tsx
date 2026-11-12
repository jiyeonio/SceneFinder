import { useEffect, useState, type FormEvent } from 'react';
import '../styles/results.css';
import { Icon } from '../components/Icon';
import { SceneRow, SourceTag, Thumb, VerifyBadge } from '../components/Common';
import { searchWelfare, type SearchResponse } from '../data/api';
import { docs } from '../data/mock';
import { go } from '../router';
import { fmt, won } from '../utils';

type Filter = 'all' | 'scenes' | 'policy' | 'screen';

export default function Results({ query }: { query: string }) {
  const [q, setQ] = useState(query);
  const [data, setData] = useState<SearchResponse | null>(null);
  const [error, setError] = useState('');
  const [filter, setFilter] = useState<Filter>('all');
  const [couple, setCouple] = useState(false);
  const [checked, setChecked] = useState<Record<string, boolean>>({ id: true });

  useEffect(() => {
    setQ(query);
    setData(null);
    setError('');
    searchWelfare(query).then(setData).catch((e: Error) => setError(e.message));
  }, [query]);

  const onSubmit = (e: FormEvent) => { e.preventDefault(); if (q.trim()) go(`/results?q=${encodeURIComponent(q.trim())}`); };

  const policy = data?.policies[0];
  const scenes = (data?.scenes ?? []).filter((s) => filter !== 'screen' || s.found.verification === 'screen');
  const showPolicy = filter === 'all' || filter === 'policy';
  const showScenes = filter !== 'policy';
  const doneCount = docs.filter((d) => checked[d.id]).length;

  return (
    <main className="page-results">
      <section className="sbar"><div className="wrap">
        <form className="srow" role="search" onSubmit={onSubmit}>
          <label className="in"><span className="sr-only">검색어</span><Icon name="search" />
            <input type="search" value={q} onChange={(e) => setQ(e.target.value)} />
          </label>
          <button className="btn btn-pri btn-lg" type="submit">다시 검색</button>
        </form>
        <div className="summ">
          <h1><em>‘{query}’</em> 공식 정책 {data?.policies.length ?? 0}건 · 영상 장면 {data?.scenes.length ?? 0}개</h1>
          {policy && <span className="upd">정책 기준 {policy.baseYear}년 · 최종 수정 {policy.updatedAt}</span>}
        </div>
        <div className="filters">
          {([
            ['all', `전체 ${(data?.policies.length ?? 0) + (data?.scenes.length ?? 0)}`],
            ['scenes', `영상 장면 ${data?.scenes.length ?? 0}`],
            ['policy', `공식 정책 ${data?.policies.length ?? 0}`],
            ['screen', '실제 화면 있는 것만'],
          ] as [Filter, string][]).map(([k, label]) => (
            <button key={k} className="chip" aria-pressed={filter === k} onClick={() => setFilter(k)}>
              {k === 'screen' && <Icon name="check" />}{label}
            </button>
          ))}
        </div>
      </div></section>

      <div className="wrap"><div className="grid">
        <div>
          {!data && !error && <p style={{ padding: '2rem 0', color: 'var(--muted)' }}>찾고 있어요…</p>}
          {error && <p style={{ padding: '2rem 0', color: 'var(--red)' }}>{error} 잠시 후 다시 시도해 주세요.</p>}

          {policy && showPolicy && (
            <article className="card pol">
              <div className="strip"><SourceTag kind="gov" />{policy.source}<span className="r">{policy.baseYear}년 기준 · 수정 {policy.updatedAt}</span></div>
              <div className="in">
                <div className="tt">
                  <div><span className="tag tag-gray">{policy.category}</span><h2>{policy.name}</h2></div>
                  <a className="btn btn-line" href="#/guide">자세한 기준 보기</a>
                </div>
                <div className="facts">
                  <div className="fact"><div className="k">받을 수 있는 분</div><div className="v">{policy.target}</div>
                    <div className="s">소득인정액이 기준 이하<br />혼자 {policy.incomeLimit.single} · 부부 {policy.incomeLimit.couple}</div></div>
                  <div className="fact"><div className="k">받는 금액</div><div className="v blue num">월 최대 {won(policy.maxAmount.single)}원</div>
                    <div className="s">혼자 사는 경우 · 부부 최대 {won(policy.maxAmount.couple)}원</div></div>
                  <div className="fact"><div className="k">신청 시기·방법</div><div className="v">{policy.applyWhen}</div>
                    <div className="s">{policy.applyWhere}</div></div>
                </div>
                <div className="acts">
                  <a className="btn btn-pri btn-lg" href={policy.applyUrl} target="_blank" rel="noreferrer">복지로에서 공식 신청하기<Icon name="ext" /></a>
                  <a className="btn btn-line btn-lg" href="#"><Icon name="print" />신청서·동의서 서식 받기</a>
                </div>
              </div>
            </article>
          )}

          {data && showScenes && (
            <>
              <div className="vh">
                <div><SourceTag kind="ai" /><h2>신청서 쓰는 장면을 찾았어요</h2></div>
                <div className="legend">
                  <VerifyBadge v="screen" />신청 화면이 영상에 나와요
                  <VerifyBadge v="subtitle" />말로만 설명해요
                </div>
              </div>

              {scenes.map((s) => {
                const sub = s.found.verification !== 'screen';
                const href = `#/watch/${s.videoId}?t=${s.found.start}`;
                return (
                  <article key={s.videoId} className="card vr">
                    <div className="meta"><b>{s.publisher}</b><span>게시 {s.publishedAt}</span><span>· 전체 {s.duration}</span></div>
                    <div className="row">
                      <Thumb href={href} type={s.thumbType} duration={s.duration} src={s.thumbnailUrl} />
                      <div>
                        <h3>{s.title}</h3>
                        <div className={`found${sub ? ' sub' : ''}`}>
                          <span className="lab"><Icon name={sub ? 'text' : 'scan'} />{sub ? 'AI가 찾은 장면 · 화면은 없어요' : 'AI가 찾은 장면'}</span>
                          <div className="tm">
                            <b className="num">{fmt(s.found.start)} – {fmt(s.found.end)}</b>
                            <span>{s.found.label}</span>
                            <VerifyBadge v={s.found.verification} />
                          </div>
                          <a className={`btn ${sub ? 'btn-line' : 'btn-pri'}`} href={href}><Icon name="play" fill />찾은 장면부터 보기</a>
                        </div>
                        {s.otherScenes && (
                          <div className="others">
                            {s.otherScenes.map((o) => <SceneRow key={o.start} href={`#/watch/${s.videoId}?t=${o.start}`} t={o.start} label={o.label} />)}
                          </div>
                        )}
                      </div>
                    </div>
                  </article>
                );
              })}
              <div className="pager"><span>‹</span><span className="on">1</span><span>2</span><span>›</span></div>
            </>
          )}
        </div>

        <aside className="side">
          <section className="card calc">
            <h3>받을 수 있을지 미리 계산</h3>
            <p className="note">소득·재산을 넣으면 예상 결과를 보여줘요. 실제 판정은 주민센터 심사로 정해져요.</p>
            <div className="seg2" role="group" aria-label="가구 유형">
              <button aria-pressed={!couple} onClick={() => setCouple(false)}>혼자 살아요</button>
              <button aria-pressed={couple} onClick={() => setCouple(true)}>부부예요</button>
            </div>
            <div className="kv"><span>2026년 소득 기준</span><b className="num">{couple ? '월 395.2만원 이하' : '월 247만원 이하'}</b></div>
            <a className="btn btn-pri btn-block" href="#" style={{ marginTop: '.8rem' }}>1분 모의계산 시작</a>
          </section>

          <section className="card">
            <h3>준비할 서류</h3>
            <p className="note">준비했는지 확인하는 용도예요. 자격 판정이 아니에요.</p>
            <div className="docs">
              {docs.map((d) => (
                <label key={d.id}>
                  <input type="checkbox" checked={!!checked[d.id]} onChange={(e) => setChecked({ ...checked, [d.id]: e.target.checked })} />
                  <span>{d.name}{d.note && <small>{d.note}</small>}</span>
                </label>
              ))}
            </div>
            <div className="prog"><div><i style={{ width: `${(doneCount / docs.length) * 100}%` }} /></div>{docs.length}개 중 {doneCount}개 준비</div>
          </section>

          <section className="card warnc">
            <h3><span style={{ display: 'flex', alignItems: 'center', gap: '.4rem' }}><Icon name="alert" style={{ color: 'var(--amber)' }} />신청 전 꼭 확인</span></h3>
            <ul>
              <li>65세 생일 달의 <b>1개월 전부터</b> 신청돼요.</li>
              <li>부부가 함께 신청하면 <b>배우자 본인 인증</b>도 필요해요.</li>
              <li>가족이 대신 신청하면 <b>위임장</b>이 있어야 해요.</li>
            </ul>
          </section>

          <section className="card">
            <h3>자주 묻는 질문</h3>
            <details open><summary>돈은 언제 들어오나요?</summary><p>매월 25일 본인 통장으로 들어와요.</p></details>
            <details><summary>자녀 소득도 보나요?</summary><p>아니요. 본인과 배우자만 봐요.</p></details>
            <details><summary>주민센터에 가기 어려워요</summary><p>국민연금공단(1355)에 방문 상담을 요청할 수 있어요.</p></details>
          </section>

          <section className="card">
            <h3>전화로 물어보기</h3>
            <a className="tel" href="tel:129"><span><small>보건복지상담센터 · 24시간</small><b>국번 없이 129</b></span><span className="c"><Icon name="phone" /></span></a>
            <a className="tel" href="tel:1355"><span><small>국민연금공단</small><b>1355</b></span><span className="c"><Icon name="phone" /></span></a>
          </section>
        </aside>
      </div></div>
    </main>
  );
}
