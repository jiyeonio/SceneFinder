import { useEffect, useMemo, useState } from 'react';
import { useYouTubePlayer } from '../components/useYouTubePlayer';
import '../styles/watch.css';
import { Icon } from '../components/Icon';
import { SourceTag, VerifyBadge } from '../components/Common';
import { getVideo, pollSearch, searchWelfare, type SearchResponse } from '../data/api';
import type { Chapter, VideoDetail } from '../data/types';
import { fmt, pct } from '../utils';

const CIRCLED = ['①', '②', '③', '④', '⑤', '⑥', '⑦', '⑧'];
const SPEEDS = [0.75, 1, 1.25];

export default function Watch({ videoId, startAt, endAt, jobId }: { videoId: string; startAt?: number; endAt?: number; jobId?: string }) {
  const [video, setVideo] = useState<VideoDetail | null>(null);
  const [loopCh, setLoopCh] = useState<Chapter | null>(null);
  const [firstAt, setFirstAt] = useState(startAt ?? 0);
  const [repeat, setRepeat] = useState(false);
  const [bigSub, setBigSub] = useState(true);
  const [speed, setSpeed] = useState(1);
  const [checked, setChecked] = useState<Record<string, boolean>>({});
  const [ask, setAsk] = useState('');
  const [asked, setAsked] = useState<SearchResponse | null>(null);
  const [asking, setAsking] = useState(false);

  useEffect(() => {
    getVideo(videoId, { jobId, t: startAt, e: endAt }).then((v) => {
      setVideo(v);
      const m = v.chapters.find((c) => c.id === v.matchedChapterId) ?? null;
      setLoopCh(m);
      setFirstAt(startAt ?? m?.start ?? 0);
    });
  }, [videoId, startAt, endAt, jobId]);

  // 검색 결과 확인(VLM)이 끝나기 전에 들어온 경우: 배지만 갱신 (재생 위치는 그대로)
  useEffect(() => {
    if (!video || !jobId || !video.chapters.some((c) => c.verification === 'pending')) return;
    const id = window.setTimeout(() => {
      getVideo(videoId, { jobId, t: startAt, e: endAt }).then((v) => setVideo((old) => (old ? { ...old, chapters: v.chapters } : v)));
    }, 1500);
    return () => window.clearTimeout(id);
  }, [video, videoId, jobId, startAt, endAt]);

  const yt = useYouTubePlayer(video?.youtubeVideoId ?? video?.videoId, firstAt);
  const time = yt.time;
  const { seek: seekYt, setRate, ready: ytReady } = yt;
  const playing = yt.playing;
  const chapters = video?.chapters ?? [];
  const shown = chapters.filter((c) => !c.gap);
  const current = useMemo(
    () => chapters.find((c) => time >= c.start && time < c.end) ?? chapters[chapters.length - 1],
    [chapters, time],
  );
  const matched = chapters.find((c) => c.id === video?.matchedChapterId);

  // 구간 반복: 마지막으로 고른 장면(loopCh)의 끝에 닿으면 처음으로
  useEffect(() => {
    if (repeat && loopCh && playing && time >= loopCh.end - 0.15) seekYt(loopCh.start);
  }, [time, repeat, loopCh, playing, seekYt]);
  useEffect(() => { setRate(speed); }, [speed, ytReady, setRate]);
  const subNow = video?.subtitles?.find((x) => time >= x.start && time < x.end)?.text;

  if (!video || !current || !matched) {
    return <main className="page-watch"><div className="wrap top"><p style={{ color: 'var(--muted)' }}>영상을 불러오고 있어요…</p></div></main>;
  }

  const total = video.durationSec;
  // 진행바 위 장면 이름: 서로 가까우면(전체의 12% 안) 하나만 보임 — 지금 보는 장면·찾은 장면을 먼저
  const labelShown = (() => {
    const order = [...shown].sort((a, b) => Number(b.id === current.id) - Number(a.id === current.id) || Number(b.id === matched.id) - Number(a.id === matched.id) || a.start - b.start);
    const kept: Chapter[] = [];
    for (const c of order) if (kept.every((k) => Math.abs(k.start - c.start) / total >= 0.12)) kept.push(c);
    return new Set(kept.map((k) => k.id));
  })();
  const policy = video.policy;
  const docs = video.docs;
  const officialSteps = video.officialSteps;
  const isMatched = current.id === matched.id;
  const follow = current.follow ?? [];
  const followIdx = follow.reduce((acc, f, i) => (time >= f.at ? i : acc), 0);
  const curIdx = shown.indexOf(current);
  const nextChapter = curIdx >= 0 ? shown[curIdx + 1] : shown.find((c) => c.start > time);
  const prevChapter = curIdx >= 0 ? shown[curIdx - 1] : [...shown].reverse().find((c) => c.end <= time);
  const seek = (t: number) => {
    const ch = shown.find((c) => t >= c.start - 0.5 && t < c.end);
    if (ch) setLoopCh(ch);
    yt.seek(t);
  };
  /** 신청 단계 카드: 그 장면으로 가서 큰 자막을 켬 (구간 반복은 사용자가 버튼을 누를 때만) */
  const seekStep = (t: number) => { setBigSub(true); seek(t); };
  /** 이 정책 맥락에서 질문 (예: 「이거 아직 신청 되는 거예요?」) — 공식 정보 답 + 영상 장면 */
  const onAsk = (e: React.FormEvent) => {
    e.preventDefault();
    const q = ask.trim(); if (!q) return;
    setAsking(true); setAsked(null);
    searchWelfare(q, policy?.policyId).then((d) => {
      setAsked(d); setAsking(false);
      const poll = (n: number) => { if (d.jobId && n < 40) window.setTimeout(() => pollSearch(d.jobId!).then((x) => { setAsked(x); if (x.status === 'pending') poll(n + 1); }), 800); };
      if (d.status === 'pending') poll(0);
    }).catch(() => setAsking(false));
  };

  return (
    <main className="page-watch">
      <div className="wrap top">
        <div className="crumb"><span>홈</span>›<span>{policy?.category ?? '복지 안내'}</span>›<span>{policy?.name ?? '영상'}</span>›<b>신청 안내 영상</b></div>
        <div className="th">
          <div>
            <div style={{ display: 'flex', gap: '.4rem', flexWrap: 'wrap' }}>
              {policy && <span className="tag tag-blue">{policy.name}</span>}<span className="tag tag-gray">{video.subtitles?.length ? '자막 있음' : '자막 없음'}</span><span className="tag tag-gray">장면 {shown.length}개</span>{video.stepsStatus === 'draft' && <span className="tag tag-gray">단계 카드 초안</span>}
            </div>
            <h1>{video.title}</h1>
          </div>
          <div className="acts">
            <button className="btn btn-line"><Icon name="bookmark" />저장</button>
            <button className="btn btn-line"><Icon name="share" />공유</button>
          </div>
        </div>
        <div className="meta">
          <span className="src src-ai"><Icon name="scan" />영상</span><b>{video.publisher}</b><span>게시 {video.publishedAt} · {fmt(total)}</span>
          <span>|</span>
          {policy && <><span className="src src-gov"><Icon name="db" />정책정보</span><span>{policy.baseYear}년 기준 · 수정 {policy.updatedAt}</span></>}
        </div>

        <div className="grid">
          <div>
            {/* 플레이어 — YouTube IFrame (useYouTubePlayer), 컨트롤은 아래 디자인 그대로 */}
            <div className="player">
              <div className="stage">
                <div className="yt" ref={yt.mountRef} />
                {yt.error && <div className="yterr">{yt.error}</div>}
                <div className="now">
                  <span><i />{isMatched ? `찾은 장면 재생 중 · ${fmt(matched.start)} – ${fmt(matched.end)}` : current.gap ? '재생 중' : `재생 중 · ${current.title}`}</span>
                </div>
              </div>
              {bigSub && <div className="ccbar" aria-live="polite">{subNow ? `“${subNow}”` : '\u00a0'}</div>}
              <div className="ctl">
                <div className="tl" aria-label="장면 타임라인">
                  {shown.map((c, i) => (
                    <span key={c.id} className={`lab${c.id === current.id ? ' on' : ''}${labelShown.has(c.id) ? '' : ' hid'}`} style={{ left: pct(c.start, total) }}>
                      {CIRCLED[i]} {c.short}
                    </span>
                  ))}
                  <div className="track" />
                  <div className="seg" style={{ left: pct(matched.start, total), width: pct(matched.end - matched.start, total) }} />
                  <div className="done" style={{ width: pct(time, total) }} />
                  {shown.map((c, i) => <span key={c.id} className="tick" title={`${CIRCLED[i]} ${c.short} · ${fmt(c.start)}`} style={{ left: pct(c.start, total) }} />)}
                  <span className="head" style={{ left: pct(time, total) }} />
                </div>
                <div className="cb">
                  <button className="pp" aria-label={playing ? '일시정지' : '재생'} onClick={yt.toggle}>
                    <Icon name={playing ? 'pause' : 'play'} fill={!playing} />
                  </button>
                  <button onClick={() => yt.seek(Math.max(0, time - 10))}><Icon name="rew" />10초 뒤로</button>
                  <span className="tm num">{fmt(time)} / {fmt(total)}</span>
                  <span className="sp" />
                  <button aria-pressed={repeat} onClick={() => setRepeat(!repeat)}><Icon name="repeat" />이 장면 반복</button>
                  <button aria-pressed={bigSub} onClick={() => setBigSub(!bigSub)}>큰 자막</button>
                  <div className="spd" role="group" aria-label="재생 속도">
                    {SPEEDS.map((s) => <button key={s} aria-pressed={speed === s} onClick={() => setSpeed(s)}>{s}배</button>)}
                  </div>
                  <button aria-label="전체 화면"><Icon name="full" /></button>
                </div>
              </div>
            </div>

            {/* 이 정책에 대해 물어보기 — 영상에 없는 내용은 공식 정보로 답함 */}
            {policy && (
              <section className="card follow" aria-label="이 정책에 대해 물어보기">
                <div className="hd"><h2>{policy.name}에 대해 물어보기</h2><p>영상에 없는 내용은 공식 정보로 답해요.</p></div>
                <form onSubmit={onAsk} style={{ display: 'flex', gap: '.5rem', marginTop: '.6rem' }}>
                  <input type="search" value={ask} onChange={(e) => setAsk(e.target.value)} placeholder="예: 이거 아직 신청 되는 거예요?"
                    aria-label="질문" style={{ flex: 1, fontSize: '1.05rem', padding: '.6rem .8rem', border: '1.5px solid var(--line-2)', borderRadius: '.6rem' }} />
                  <button className="btn btn-pri" type="submit" disabled={asking}>{asking ? '찾는 중…' : '물어보기'}</button>
                </form>
                {asked && (
                  <div style={{ marginTop: '.8rem' }}>
                    {asked.notice?.show && (
                      <div className="warn" role="status"><Icon name="alert" style={{ color: 'var(--amber)' }} /><span><b>영상에는 해당 내용이 없어요.</b> 공식 정보를 확인하세요.</span></div>
                    )}
                    {asked.official && asked.official.items.length > 0 && (
                      <div style={{ marginTop: '.6rem' }}>
                        <SourceTag kind="gov" />
                        {asked.official.items.map((it) => (
                          <p key={it.field} style={{ whiteSpace: 'pre-line', margin: '.4rem 0' }}>
                            <b>{({ applyWhen: '신청 기간', updatedAt: '정보 수정일', requiredDocs: '구비서류', applyMethod: '신청 방법', applyUrl: '공식 신청 페이지', targetDetail: '지원 대상', criteria: '선정 기준', amount: '금액', benefit: '지원 내용' } as Record<string, string>)[it.field] ?? it.field}</b>{' '}
                            {Array.isArray(it.value) ? (it.value as (string | { name?: string; label?: string; value?: string })[]).map((x) => typeof x === 'string' ? x : x.name ?? `${x.label} ${x.value}`).join(' · ') : String(it.value)}
                          </p>
                        ))}
                        <small style={{ color: 'var(--muted)' }}>출처 {asked.official.source} · {asked.official.baseYear}년 기준 · 수정 {asked.official.updatedAt}</small>
                      </div>
                    )}
                    {!asked.notice?.show && asked.scenes.slice(0, 3).map((sc) => (
                      <div key={sc.videoId} className="fs" style={{ marginTop: '.5rem' }}>
                        <span className="n"><Icon name="play" fill /></span>
                        <div><b>{sc.title}</b><p>{fmt(sc.found.start)} · {sc.found.label}</p><VerifyBadge v={sc.found.verification} /></div>
                        {sc.videoId === video.videoId
                          ? <a className="lk" href="#" onClick={(e) => { e.preventDefault(); seek(sc.found.start); }}><Icon name="play" fill /><span className="num">{fmt(sc.found.start)}</span></a>
                          : <a className="lk" href={`#/watch/${sc.videoId}?t=${sc.found.start}&e=${sc.found.end}${asked.jobId ? `&job=${asked.jobId}` : ''}`}><Icon name="play" fill /><span className="num">{fmt(sc.found.start)}</span></a>}
                      </div>
                    ))}
                  </div>
                )}
              </section>
            )}

            {/* 장면 목록 */}
            <section className="card chap">
              <div className="hd"><h2>영상 장면</h2><p>누르면 그 시간부터 재생돼요.</p></div>
              {shown.map((c) => (
                <div key={c.id} className="ch" aria-current={c.id === current.id ? 'true' : undefined}>
                  <div className="t num">{fmt(c.start)} – {fmt(c.end)}<small>{c.stepLabel}{c.id === matched.id ? ' · 찾은 장면' : ''}</small></div>
                  <div>
                    <b>{c.title}</b>
                    <div className="bd">
                      <VerifyBadge v={c.verification} long={c.step !== null} />
                      {c.id === current.id && <span className="tag tag-dark">재생 중</span>}
                    </div>
                  </div>
                  <button className="go" onClick={() => (c.step ? seekStep(c.start) : seek(c.start))}><Icon name="play" fill />{c.id === current.id ? '처음부터' : '여기부터'}</button>
                </div>
              ))}
              <div className="fb"><span>장면 구분과 검증 상태는 AI 분석 결과라 틀릴 수 있어요.</span><a href="#">장면이 다르면 알려주기</a></div>
            </section>

            {/* 이 장면 따라 하기 */}
            <section className="card follow">
              <div className="hd">
                <h2>이 장면 따라 하기</h2>
                <span className="tag tag-blue">{current.stepLabel} · {current.title}</span>
                <p>{follow.length ? '영상에 나온 순서예요' : ''}</p>
              </div>
              {follow.map((f, i) => (
                <div key={f.title} className={`fs${i < followIdx ? ' done' : i === followIdx ? ' now' : ''}`}>
                  <span className="n">{i < followIdx ? <Icon name="check" /> : i + 1}</span>
                  <div>
                    {i === followIdx && <span className="st">지금 영상에서 보는 중</span>}
                    <b>{f.title}</b>
                    <p>{f.desc}</p>
                  </div>
                  <a className="lk" href="#" onClick={(e) => { e.preventDefault(); seek(f.at); }}><Icon name="play" fill /><span className="num">{fmt(f.at)}</span></a>
                </div>
              ))}
              {!follow.length && (
                <div className="warn" style={{ marginTop: '1rem' }}><Icon name="info" style={{ color: 'var(--muted)' }} />
                  <span>{current.verification === 'subtitle'
                    ? '이 장면은 말로만 설명하고 실제 화면은 나오지 않아요. 오른쪽 공식 안내를 확인하세요.'
                    : '이 장면은 신청 단계가 아니에요. 다음 장면으로 넘어가 보세요.'}</span>
                </div>
              )}
              {current.id === matched.id && (
                <div className="warn"><Icon name="info" style={{ color: 'var(--muted)' }} /><span>제출한 뒤 결과를 확인하는 화면은 이 영상에 없어요. 4단계는 오른쪽 공식 안내를 확인하세요.</span></div>
              )}
              <div className="nx">
                {prevChapter ? <button className="btn btn-line" onClick={() => seek(prevChapter.start)}><Icon name="back" />{prevChapter.title}</button> : <span />}
                {nextChapter && <button className="btn btn-dark" onClick={() => seek(nextChapter.start)}>{nextChapter.title}<Icon name="arrow" /></button>}
              </div>
            </section>
          </div>

          {/* 오른쪽 공식 정책정보 (공공데이터 항목) */}
          {policy && <aside className="card pp-card" aria-label="공식 정책정보">
            <div className="hd">
              <div className="r1"><SourceTag kind="gov" /><span style={{ fontSize: '.8rem', color: 'var(--muted)' }}>{policy.baseYear}년 기준</span></div>
              <h2>{policy.name}</h2>
              <p>출처 {policy.source} · 수정 {policy.updatedAt}</p>
            </div>
            <div className="blk"><h3><span className="n">1</span>받을 수 있는 분</h3>
              <p style={{ whiteSpace: 'pre-line' }}>{policy.targetDetail || policy.target}</p></div>
            <div className="blk"><details>
              <summary><span className="n">2</span>선정 기준<span className="r">자세히<Icon name="chev" /></span></summary>
              <p style={{ whiteSpace: 'pre-line' }}>{policy.criteria}</p>
            </details></div>
            {policy.amount && policy.amount.length > 0 ? (
              <div className="blk"><h3><span className="n">3</span>받는 금액</h3>
                {policy.amount.map((a, i) => (
                  <div key={a.label} className="money" style={i ? { marginTop: '.1rem' } : undefined}><span>{a.label}</span><b className="num" style={i ? { fontSize: '1.1rem', color: 'var(--ink)' } : undefined}>{a.value}</b></div>
                ))}
                <details><summary>지원 내용 전체<span className="r"><Icon name="chev" /></span></summary><p style={{ whiteSpace: 'pre-line' }}>{policy.benefit}</p></details></div>
            ) : (
              <div className="blk"><details open>
                <summary><span className="n">3</span>지원 내용<span className="r"><Icon name="chev" /></span></summary>
                <p style={{ whiteSpace: 'pre-line' }}>{policy.benefit}</p>
              </details></div>
            )}
            <div className="blk"><details>
              <summary><span className="n">4</span>신청 방법·시기<span className="r">{policy.applyWhen}<Icon name="chev" /></span></summary>
              <p style={{ whiteSpace: 'pre-line' }}>{policy.applyMethod}</p>
            </details></div>
            <div className="blk"><h3><span className="n">5</span>준비 서류 확인</h3>
              <div className="docs">
                {docs.map((d) => (
                  <label key={d.id} className={current.relatedDocs.includes(d.id) ? 'rel' : ''}>
                    <input type="checkbox" checked={!!checked[d.id]} onChange={(e) => setChecked({ ...checked, [d.id]: e.target.checked })} />
                    <span>{d.name}</span>
                    {current.relatedDocs.includes(d.id) && <span className="tag tag-blue">이 장면</span>}
                  </label>
                ))}
              </div>
              <p className="note">준비 여부를 확인하는 용도예요. 자격을 판정하지 않아요.</p></div>
            <div className="blk"><h3><span className="n">6</span>공식 신청 단계</h3>
              <ol className="flow">
                {officialSteps.map((s) => {
                  const cur = current.step ?? 0;
                  const state = s.step < cur ? 'done' : s.step === cur ? 'now' : '';
                  return (
                    <li key={s.step} className={state} style={s.videoAt !== undefined ? { cursor: 'pointer' } : undefined}
                      onClick={s.videoAt !== undefined ? () => seekStep(s.videoAt!) : undefined}>
                      <span className="d">{state === 'done' ? <Icon name="check" style={{ width: '.8rem', height: '.8rem' }} /> : s.step}</span>
                      <div>
                        <b>{s.title}{state === 'now' ? ' · 지금 보는 중' : ''}</b>
                        <small>
                          {s.videoAt !== undefined && <a href="#" onClick={(e) => { e.preventDefault(); e.stopPropagation(); seekStep(s.videoAt!); }}>영상 {fmt(s.videoAt)}부터 보기 </a>}
                          {s.verification === 'subtitle' && <span className="vb vb-sub" style={{ fontSize: '.72rem', padding: '0 .4rem' }}>자막에서 확인됨</span>}
                          {s.videoAt === undefined && <span className="vb vb-none" style={{ fontSize: '.72rem', padding: '0 .4rem' }}>해당 장면 없음</span>}
                          {s.verification !== 'screen' && ` ${s.note}`}
                        </small>
                      </div>
                    </li>
                  );
                })}
              </ol></div>
            <div className="blk"><h3><span className="n">7</span>문의·공식 링크</h3>
              <p>{policy.contact}</p>
              {policy.officialUrls.map((u) => <p key={u.url}><a href={u.url} target="_blank" rel="noreferrer">{u.label}<Icon name="ext" /></a></p>)}
            </div>
            <div className="cta">
              <a className="btn btn-pri btn-lg btn-block" href={policy.applyUrl} target="_blank" rel="noreferrer">공식 신청 페이지로<Icon name="ext" /></a>
              <div className="two">
                <a className="btn btn-line" href="https://www.gov.kr" target="_blank" rel="noreferrer"><Icon name="pin" />주민센터 찾기</a>
                <a className="btn btn-line" href="tel:129"><Icon name="phone" />129 상담</a>
              </div>
              <p>신청은 공식 기관 사이트에서 이뤄져요. 복지바로봄은 개인정보를 받지 않아요. 자격·금액·기간은 공식 정보를 기준으로 하세요.</p>
            </div>
          </aside>}
        </div>
      </div>
    </main>
  );
}
