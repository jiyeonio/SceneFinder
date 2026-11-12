import { useEffect, useState, type FormEvent } from 'react';
import '../styles/results.css';
import { Icon } from '../components/Icon';
import { SceneRow, SourceTag, Thumb, VerifyBadge } from '../components/Common';
import { pollSearch, searchWelfare, type SearchResponse } from '../data/api';
import type { SceneResult, Verification } from '../data/types';
import { go } from '../router';
import { contacts, fmt } from '../utils';

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
  const [open, setOpen] = useState<Record<string, boolean>>({});
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
  const official = data?.official;
  const notice = data?.notice;
  const pending = data?.status === 'pending';
  // 장면 순서: 확인이 끝나면 화면에서 확인됨 → 자막에서 확인됨 → (확인 안 됨은 맨 아래 접어 둠)
  const RANK: Record<Verification, number> = { screen: 0, subtitle: 1, pending: 2, none: 3 };
  const all = (data?.scenes ?? []).filter((s) => filter !== 'screen' || s.found.verification === 'screen');
  const ranked = pending ? all : [...all].sort((a, b) => RANK[a.found.verification] - RANK[b.found.verification]);
  const good = pending ? ranked : ranked.filter((s) => s.found.verification !== 'none');
  const weak = pending ? [] : ranked.filter((s) => s.found.verification === 'none');
  const top = notice?.show ? undefined : good[0];
  const rest = notice?.show ? good : good.slice(1);
  const showPolicy = filter === 'all' || filter === 'policy';
  const showScenes = filter !== 'policy';
  // 구비서류는 한 곳에만: 서류를 물으면 위 공식 답변(누르면 체크), 아니면 오른쪽 체크리스트
  const docsInAnswer = !!official?.items.some((it) => it.field === 'requiredDocs');
  const docs = (policy?.requiredDocs ?? []).map((name, i) => ({ id: `d${i}`, name }));
  const doneCount = docs.filter((d) => checked[d.id]).length;
  const job = data?.jobId ? `&job=${data.jobId}` : '';
  const hrefOf = (s: SceneResult, t = s.found.start, e: number | undefined = s.found.end) => `#/watch/${s.videoId}?t=${t}${e ? `&e=${e}` : ''}${job}`;
  const answerItems = (official?.items ?? []).filter((it) => it.field !== 'updatedAt');

  const moreScenes = (s: SceneResult) => s.otherScenes && s.otherScenes.length > 0 && (
    <>
      <button className="btn btn-line" style={{ minHeight: '2.3rem', marginTop: '.6rem' }} aria-expanded={!!open[s.videoId]}
        onClick={() => setOpen({ ...open, [s.videoId]: !open[s.videoId] })}>
        {open[s.videoId] ? '접기' : `이 영상의 다른 장면 ${s.otherScenes.length}개 더 보기`}
      </button>
      {open[s.videoId] && (
        <div className="others">
          {s.otherScenes.map((o) => <SceneRow key={o.start} href={hrefOf(s, o.start, o.end)} t={o.start} label={o.label} />)}
        </div>
      )}
    </>
  );

  const smallCard = (s: SceneResult) => (
    <article key={s.videoId} className="card vr mini">
      <Thumb href={hrefOf(s)} type={s.thumbType} duration={s.duration} src={s.thumbnailUrl} />
      <h3>{s.title}</h3>
      <div className="meta"><b>{s.publisher}</b><span>· 게시 {s.publishedAt}</span></div>
      <div className="tm"><b className="num">{fmt(s.found.start)} – {fmt(s.found.end)}</b><VerifyBadge v={s.found.verification} /></div>
      <a className="btn btn-line" href={hrefOf(s)}><Icon name="play" fill />이 장면 보기</a>
      {moreScenes(s)}
    </article>
  );

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
          <h1><em>‘{query}’</em> 영상 장면 {data?.scenes.length ?? 0}개 · 공식 정책 {data?.policies.length ?? 0}건</h1>
          {pending && <VerifyBadge v="pending" />}
        </div>
        <div className="filters">
          {([['all', '전체'], ['scenes', '영상 장면'], ['policy', '공식 정책'], ['screen', '화면에서 확인된 것만']] as [Filter, string][]).map(([k, label]) => (
            <button key={k} className="chip" aria-pressed={filter === k} onClick={() => setFilter(k)}>{k === 'screen' && <Icon name="check" />}{label}</button>
          ))}
        </div>
      </div></section>

      <div className="wrap">
        {!data && !error && <p style={{ padding: '2rem 0', color: 'var(--muted)' }}>찾고 있어요…</p>}
        {error && <p style={{ padding: '2rem 0', color: 'var(--red)' }}>{error} 잠시 후 다시 시도해 주세요.</p>}

        {/* 바로 답: 왼쪽 1위 장면, 오른쪽 공식 답변 */}
        {data && (
          <section className="ans" aria-label="바로 답">
            {showScenes && (top ? (
              <article className="card vr ans-scene">
                <div className="vh0"><SourceTag kind="ai" /><span>{pending ? 'AI가 찾은 장면 · 화면 확인 중' : 'AI가 찾은 장면'}</span></div>
                <Thumb href={hrefOf(top)} type={top.thumbType} duration={top.duration} src={top.thumbnailUrl} />
                <h3>{top.title}</h3>
                <div className="meta"><b>{top.publisher}</b><span>· 게시 {top.publishedAt}</span><span>· 전체 {top.duration}</span></div>
                <div className={`found${top.found.verification === 'subtitle' ? ' sub' : ''}`}>
                  <div className="tm"><b className="num">{fmt(top.found.start)} – {fmt(top.found.end)}</b><VerifyBadge v={top.found.verification} /></div>
                  <span className="ev">{top.found.label}</span>
                  <a className="btn btn-pri btn-lg" href={hrefOf(top)}><Icon name="play" fill />찾은 장면부터 보기</a>
                </div>
                {moreScenes(top)}
              </article>
            ) : (
              <article className="card warnc ans-scene" role="status">
                <h3><span style={{ display: 'flex', alignItems: 'center', gap: '.4rem' }}><Icon name="alert" style={{ color: 'var(--amber)' }} />영상에는 해당 내용이 없어요</span></h3>
                <p>{notice?.message || '영상에서 확인된 장면이 없어요. 공식 정보를 확인하세요.'}</p>
              </article>
            ))}
            <div className="ans-col">
            {(answerItems.length > 0 || policy) && (
              <article className="card pol ans-off">
                <div className="strip"><SourceTag kind="gov" />공식 답변</div>
                <div className="in">
                  {answerItems.length > 0 ? answerItems.map((it) => (
                    <div key={it.field} className="ai">
                      <div className="k">{FIELD_LABEL[it.field] ?? it.field}{it.field === 'requiredDocs' && docs.length > 0 && <span> · {docs.length}개 중 {doneCount}개 준비</span>}</div>
                      {it.field === 'requiredDocs' ? (
                        <div className="chips">
                          {docs.map((d) => (
                            <button key={d.id} className="chip" aria-pressed={!!checked[d.id]} onClick={() => setChecked({ ...checked, [d.id]: !checked[d.id] })}>
                              {checked[d.id] && <Icon name="check" />}{d.name}
                            </button>
                          ))}
                        </div>
                      ) : it.field === 'applyUrl' ? (
                        <a className="btn btn-line" href={String(it.value)} target="_blank" rel="noreferrer">공식 신청 페이지<Icon name="ext" /></a>
                      ) : it.field === 'amount' && Array.isArray(it.value) ? (
                        <div className="v">{(it.value as { label: string; value: string }[]).map((a) => `${a.label} ${a.value}`).join(' · ')}</div>
                      ) : (
                        <div className="v">{firstLine(String(it.value))}</div>
                      )}
                    </div>
                  )) : policy && (
                    <div className="ai"><div className="k">{policy.name}</div><div className="v">{firstLine(policy.targetDetail) || policy.target}</div></div>
                  )}
                  {docsInAnswer && <p className="note">누르면 준비한 서류로 표시돼요. 자격 판정이 아니에요.</p>}
                  <p className="src1">출처 {official?.source ?? policy?.source} · {official?.baseYear ?? policy?.baseYear}년 기준 · 수정 {official?.updatedAt ?? policy?.updatedAt}</p>
                </div>
              </article>
            )}
            {/* 문의: 정책 API 문의처 그대로 */}
            {policy && contacts(policy.contact).length > 0 && (
              <section className="card">
                <h3>문의</h3>
                {contacts(policy.contact).map((c) => c.tel ? (
                  <a key={c.name + c.tel} className="tel" href={`tel:${c.tel.replace(/-/g, '')}`}><span><small>{c.name}</small><b>{c.tel}</b></span><span className="c"><Icon name="phone" /></span></a>
                ) : <p key={c.name} className="note">{c.name}</p>)}
                <p className="note" style={{ marginTop: '.6rem' }}>출처 {policy.source} · {policy.name} 문의처 · 수정 {policy.updatedAt}</p>
              </section>
            )}
            {!docsInAnswer && docs.length > 0 && (
              <section className="card">
                <h3>준비 서류 체크리스트</h3>
                <p className="note">준비했는지 확인하는 용도예요. 자격 판정이 아니에요.</p>
                <div className="docs">
                  {docs.map((d) => (
                    <label key={d.id}>
                      <input type="checkbox" checked={!!checked[d.id]} onChange={(e) => setChecked({ ...checked, [d.id]: e.target.checked })} />
                      <span>{d.name}</span>
                    </label>
                  ))}
                </div>
                <div className="prog"><div><i style={{ width: `${(doneCount / docs.length) * 100}%` }} /></div>{docs.length}개 중 {doneCount}개 준비</div>
                {policy && <p className="note">출처 {policy.source} · 수정 {policy.updatedAt}</p>}
              </section>
            )}
            </div>
          </section>
        )}

        <div className="grid one">
          <div>
            {/* 다른 영상 장면 */}
            {data && showScenes && rest.length > 0 && (
              <>
                <div className="vh"><div><SourceTag kind="ai" /><h2>다른 영상 장면</h2></div></div>
                <div className="minis">{rest.map(smallCard)}</div>
              </>
            )}
            {data && showScenes && weak.length > 0 && (
              <details className="weak">
                <summary>화면·자막에서 확인되지 않은 장면 {weak.length}개</summary>
                <div className="minis">{weak.map(smallCard)}</div>
              </details>
            )}

            {/* 정책 요약 */}
            {policy && showPolicy && (
              <article className="card pol" style={{ marginTop: '2rem' }}>
                <div className="strip"><SourceTag kind="gov" />{policy.source}<span className="r">{policy.baseYear}년 기준 · 수정 {policy.updatedAt}</span></div>
                <div className="in">
                  <div className="tt">
                    <div><span className="tag tag-gray">{policy.category}</span><h2>{policy.name}</h2></div>
                    <a className="btn btn-pri" href={policy.applyUrl} target="_blank" rel="noreferrer">공식 신청하기<Icon name="ext" /></a>
                  </div>
                  <div className="facts">
                    <div className="fact"><div className="k">받을 수 있는 분</div><div className="v">{firstLine(policy.targetDetail) || policy.target}</div></div>
                    {policy.amount && policy.amount.length > 0 ? (
                      <div className="fact"><div className="k">받는 금액</div><div className="v blue num">{policy.amount[0].label.replace(/\(.*\)/, '')} {policy.amount[0].value}</div>
                        <div className="s">{policy.amount.slice(1).map((a) => `${a.label} ${a.value}`).join(' · ')}</div></div>
                    ) : (
                      <div className="fact"><div className="k">지원 내용</div><div className="v">{firstLine(policy.benefit)}</div></div>
                    )}
                    <div className="fact"><div className="k">신청 방법</div><div className="v">{firstLine(policy.applyMethod)}</div><div className="s">{policy.applyWhen}</div></div>
                  </div>
                  <details style={{ marginTop: '1rem' }}>
                    <summary>자세히 보기 (지원 대상·선정 기준·지원 내용·신청 방법 원문)</summary>
                    {([['지원 대상', policy.targetDetail], ['선정 기준', policy.criteria], ['지원 내용', policy.benefit], ['신청 방법', policy.applyMethod]] as [string, string][]).map(([k, v]) => v && (
                      <div key={k} style={{ marginTop: '.8rem' }}><b>{k}</b><p style={{ whiteSpace: 'pre-line' }}>{v}</p></div>
                    ))}
                    <p>{policy.officialUrls.map((u) => <a key={u.url} href={u.url} target="_blank" rel="noreferrer" style={{ marginRight: '1rem' }}>{u.label}<Icon name="ext" /></a>)}</p>
                  </details>
                </div>
              </article>
            )}
          </div>

        </div>
      </div>
    </main>
  );
}
