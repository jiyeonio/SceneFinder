import { useEffect, useState, type FormEvent } from 'react';
import '../styles/results.css';
import { Icon } from '../components/Icon';
import { SceneRow, SourceTag, Thumb, VerifyBadge } from '../components/Common';
import { pollSearch, searchWelfare, type SearchResponse } from '../data/api';
import { go } from '../router';
import { fmt } from '../utils';

const FIELD_LABEL: Record<string, string> = {
  requiredDocs: '구비서류', applyWhen: '신청 기간', updatedAt: '정보 수정일', applyMethod: '신청 방법', applyUrl: '공식 신청 페이지',
  targetDetail: '지원 대상', criteria: '선정 기준', amount: '금액', benefit: '지원 내용',
};
const firstLine = (t?: string) => (t ?? '').split('\n').map((x) => x.replace(/^[\s○ㅇ◦•\-·※*]+/, '').trim()).filter(Boolean)[0] ?? '';

type Filter = 'all' | 'scenes' | 'policy' | 'screen';

export default function Results({ query, policyCtx }: { query: string; policyCtx?: string }) {
  const [q, setQ] = useState(query);
  const [data, setData] = useState<SearchResponse | null>(null);
  const [error, setError] = useState('');
  const [filter, setFilter] = useState<Filter>('all');
  const [couple, setCouple] = useState(false);
  const [checked, setChecked] = useState<Record<string, boolean>>({});

  useEffect(() => {
    setQ(query);
    setData(null);
    setError('');
    let stop = false;
    let timer = 0;
    const poll = (jobId: string, n: number) => {
      timer = window.setTimeout(() => {
        pollSearch(jobId).then((d) => {
          if (stop) return;
          setData(d);
          if (d.status === 'pending' && n < 40) poll(jobId, n + 1);
        }).catch(() => undefined);
      }, 800);
    };
    searchWelfare(query, policyCtx).then((d) => {
      if (stop) return;
      setData(d);
      if (d.status === 'pending' && d.jobId) poll(d.jobId, 0);
    }).catch((e: Error) => setError(e.message));
    return () => { stop = true; window.clearTimeout(timer); };
  }, [query, policyCtx]);

  const onSubmit = (e: FormEvent) => { e.preventDefault(); if (q.trim()) go(`/results?q=${encodeURIComponent(q.trim())}`); };

  const policy = data?.policies[0];
  const scenes = (data?.scenes ?? []).filter((s) => filter !== 'screen' || s.found.verification === 'screen');
  const showPolicy = filter === 'all' || filter === 'policy';
  const showScenes = filter !== 'policy';
  const docs = (policy?.requiredDocs ?? []).map((name, i) => ({ id: `d${i}`, name, note: undefined as string | undefined }));
  const doneCount = docs.filter((d) => checked[d.id]).length;
  const isPension = policy?.policyId === 'basic-pension';
  const official = data?.official;
  const notice = data?.notice;

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

          {notice?.show && (
            <section className="card warnc" role="status">
              <h3><span style={{ display: 'flex', alignItems: 'center', gap: '.4rem' }}><Icon name="alert" style={{ color: 'var(--amber)' }} />영상에는 해당 내용이 없어요</span></h3>
              <p>{notice.message}</p>
            </section>
          )}

          {official && official.items.length > 0 && (
            <article className="card pol">
              <div className="strip"><SourceTag kind="gov" />공식 정보로 답해요<span className="r">{official.baseYear}년 기준 · 수정 {official.updatedAt}</span></div>
              <div className="in">
                <div className="facts">
                  {official.items.map((it) => (
                    <div className="fact" key={it.field}><div className="k">{FIELD_LABEL[it.field] ?? it.field}</div>
                      <div className="v" style={{ fontSize: '1rem', whiteSpace: 'pre-line' }}>
                        {Array.isArray(it.value)
                          ? (it.value as (string | { name?: string; label?: string; value?: string })[]).map((x) => typeof x === 'string' ? x : x.name ?? `${x.label} ${x.value}`).join(' · ')
                          : it.field === 'applyUrl' ? <a href={String(it.value)} target="_blank" rel="noreferrer">{String(it.value)}</a> : String(it.value)}
                      </div></div>
                  ))}
                </div>
                <p className="note" style={{ marginTop: '.6rem' }}>출처 {official.source}</p>
              </div>
            </article>
          )}

          {policy && showPolicy && (
            <article className="card pol">
              <div className="strip"><SourceTag kind="gov" />{policy.source}<span className="r">{policy.baseYear}년 기준 · 수정 {policy.updatedAt}</span></div>
              <div className="in">
                <div className="tt">
                  <div><span className="tag tag-gray">{policy.category}</span><h2>{policy.name}</h2></div>
                  <a className="btn btn-line" href="#/guide">자세한 기준 보기</a>
                </div>
                <div className="facts">
                  <div className="fact"><div className="k">받을 수 있는 분</div><div className="v">{firstLine(policy.targetDetail) || policy.target}</div>
                    <div className="s">{firstLine(policy.criteria)}</div></div>
                  {policy.amount && policy.amount.length > 0 ? (
                    <div className="fact"><div className="k">받는 금액</div><div className="v blue num">{policy.amount[0].label.replace(/\(.*\)/, '')} {policy.amount[0].value}</div>
                      <div className="s">{policy.amount.slice(1).map((a) => `${a.label} ${a.value}`).join(' · ')}</div></div>
                  ) : (
                    <div className="fact"><div className="k">지원 내용</div><div className="v">{firstLine(policy.benefit)}</div></div>
                  )}
                  <div className="fact"><div className="k">신청 시기·방법</div><div className="v">{policy.applyWhen}</div>
                    <div className="s">{firstLine(policy.applyMethod)}</div></div>
                </div>
                <div className="acts">
                  <a className="btn btn-pri btn-lg" href={policy.applyUrl} target="_blank" rel="noreferrer">복지로에서 공식 신청하기<Icon name="ext" /></a>
                  {policy.officialUrls[0] && <a className="btn btn-line btn-lg" href={policy.officialUrls[0].url} target="_blank" rel="noreferrer">{policy.officialUrls[0].label}<Icon name="ext" /></a>}
                </div>
              </div>
            </article>
          )}

          {data && showScenes && (
            <>
              <div className="vh">
                <div><SourceTag kind="ai" /><h2>{data.status === 'pending' ? '찾은 장면을 AI가 화면에서 확인하고 있어요' : '질문과 맞는 장면을 찾았어요'}</h2></div>
                <div className="legend">
                  <VerifyBadge v="screen" />신청 화면이 영상에 나와요
                  <VerifyBadge v="subtitle" />말로만 설명해요
                </div>
              </div>

              {scenes.map((s) => {
                const sub = s.found.verification === 'subtitle' || s.found.verification === 'none';
                const job = data.jobId ? `&job=${data.jobId}` : '';
                const href = `#/watch/${s.videoId}?t=${s.found.start}${job}`;
                return (
                  <article key={s.videoId} className="card vr">
                    <div className="meta"><b>{s.publisher}</b><span>게시 {s.publishedAt}</span><span>· 전체 {s.duration}</span></div>
                    <div className="row">
                      <Thumb href={href} type={s.thumbType} duration={s.duration} src={s.thumbnailUrl} />
                      <div>
                        <h3>{s.title}</h3>
                        <div className={`found${sub ? ' sub' : ''}`}>
                          <span className="lab"><Icon name={sub ? 'text' : 'scan'} />{s.found.verification === 'subtitle' ? 'AI가 찾은 장면 · 화면은 없어요' : s.found.verification === 'none' ? 'AI가 찾은 장면 · 확인되지 않음' : 'AI가 찾은 장면'}</span>
                          <div className="tm">
                            <b className="num">{fmt(s.found.start)} – {fmt(s.found.end)}</b>
                            <span>{s.found.label}</span>
                            <VerifyBadge v={s.found.verification} />
                          </div>
                          <a className={`btn ${sub ? 'btn-line' : 'btn-pri'}`} href={href}><Icon name="play" fill />찾은 장면부터 보기</a>
                        </div>
                        {s.otherScenes && (
                          <div className="others">
                            {s.otherScenes.map((o) => <SceneRow key={o.start} href={`#/watch/${s.videoId}?t=${o.start}${job}`} t={o.start} label={o.label} />)}
                          </div>
                        )}
                      </div>
                    </div>
                  </article>
                );
              })}
            </>
          )}
        </div>

        <aside className="side">
          {isPension && <section className="card calc">
            <h3>받을 수 있을지 미리 계산</h3>
            <p className="note">소득·재산을 넣으면 예상 결과를 보여줘요. 실제 판정은 주민센터 심사로 정해져요.</p>
            <div className="seg2" role="group" aria-label="가구 유형">
              <button aria-pressed={!couple} onClick={() => setCouple(false)}>혼자 살아요</button>
              <button aria-pressed={couple} onClick={() => setCouple(true)}>부부예요</button>
            </div>
            <div className="kv"><span>2026년 소득 기준</span><b className="num">{couple ? '월 395.2만원 이하' : '월 247만원 이하'}</b></div>
            <a className="btn btn-pri btn-block" href="https://basicpension.mohw.go.kr" target="_blank" rel="noreferrer" style={{ marginTop: '.8rem' }}>1분 모의계산 시작</a>
          </section>}

          {docs.length > 0 && <section className="card">
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
            {policy && <p className="note">출처 {policy.source} · 수정 {policy.updatedAt}</p>}
          </section>}

          {isPension && <section className="card warnc">
            <h3><span style={{ display: 'flex', alignItems: 'center', gap: '.4rem' }}><Icon name="alert" style={{ color: 'var(--amber)' }} />신청 전 꼭 확인</span></h3>
            <ul>
              <li>65세 생일 달의 <b>1개월 전부터</b> 신청돼요.</li>
              <li>부부가 함께 신청하면 <b>배우자 본인 인증</b>도 필요해요.</li>
              <li>가족이 대신 신청하면 <b>위임장</b>이 있어야 해요.</li>
            </ul>
          </section>}

          {isPension && <section className="card">
            <h3>자주 묻는 질문</h3>
            <details open><summary>돈은 언제 들어오나요?</summary><p>매월 25일 본인 통장으로 들어와요.</p></details>
            <details><summary>자녀 소득도 보나요?</summary><p>아니요. 본인과 배우자만 봐요.</p></details>
            <details><summary>주민센터에 가기 어려워요</summary><p>국민연금공단(1355)에 방문 상담을 요청할 수 있어요.</p></details>
          </section>}

          <section className="card">
            <h3>전화로 물어보기</h3>
            <a className="tel" href="tel:129"><span><small>보건복지상담센터 · 24시간</small><b>국번 없이 129</b></span><span className="c"><Icon name="phone" /></span></a>
            {policy?.contact && <p className="note">{policy.name} 문의: {policy.contact}</p>}
          </section>
        </aside>
      </div></div>
    </main>
  );
}
