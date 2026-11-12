import { useEffect, useMemo, useState } from 'react';
import { useYouTubePlayer } from '../components/useYouTubePlayer';
import '../styles/watch.css';
import { Icon } from '../components/Icon';
import { SourceTag, VerifyBadge } from '../components/Common';
import { getVideo } from '../data/api';
import type { Chapter, VideoDetail } from '../data/types';
import { fmt, pct } from '../utils';

const CIRCLED = ['①', '②', '③', '④', '⑤', '⑥', '⑦', '⑧'];
const SPEEDS = [0.75, 1, 1.25];

export default function Watch({ videoId, startAt, jobId }: { videoId: string; startAt?: number; jobId?: string }) {
  const [video, setVideo] = useState<VideoDetail | null>(null);
  const [loopCh, setLoopCh] = useState<Chapter | null>(null);
  const [firstAt, setFirstAt] = useState(startAt ?? 0);
  const [repeat, setRepeat] = useState(true);
  const [bigSub, setBigSub] = useState(true);
  const [speed, setSpeed] = useState(1);
  const [checked, setChecked] = useState<Record<string, boolean>>({});

  useEffect(() => {
    getVideo(videoId, { jobId, t: startAt }).then((v) => {
      setVideo(v);
      const m = v.chapters.find((c) => c.id === v.matchedChapterId) ?? null;
      setLoopCh(m);
      setFirstAt(startAt ?? m?.start ?? 0);
    });
  }, [videoId, startAt, jobId]);

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
  const policy = video.policy;
  const docs = video.docs;
  const officialSteps = video.officialSteps;
  const isMatched = current.id === matched.id;
  const follow = current.follow ?? [];
  const followIdx = follow.reduce((acc, f, i) => (time >= f.at ? i : acc), 0);
  const nextFollow = follow[followIdx + 1];
  const curIdx = shown.indexOf(current);
  const nextChapter = curIdx >= 0 ? shown[curIdx + 1] : shown.find((c) => c.start > time);
  const prevChapter = curIdx >= 0 ? shown[curIdx - 1] : [...shown].reverse().find((c) => c.end <= time);
  const seek = (t: number) => {
    const ch = shown.find((c) => t >= c.start - 0.5 && t < c.end);
    if (ch) setLoopCh(ch);
    yt.seek(t);
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

        {/* 지금 위치: 찾은 장면 / 지금 / 다음 */}
        <div className="where" aria-label="지금 위치">
          <div className="w1">
            <small><Icon name="search" />내가 찾은 장면</small>
            <b className="num">{fmt(matched.start)} – {fmt(matched.end)} · {matched.title.replace('복지로에서 ', '')}</b>
            {video.query && <span>“{video.query}”</span>}
          </div>
          <div className="w2">
            <small><Icon name="play" />지금 보는 단계</small>
            <b>{current.gap ? '영상 보는 중' : `${current.step ? `${current.step}단계` : current.stepLabel} · ${follow[followIdx]?.title ?? current.title}`}</b>
            {!current.gap && <span><VerifyBadge v={current.verification} long /></span>}
          </div>
          <div className="w3">
            <small><Icon name="arrow" />다음에 할 일</small>
            {nextFollow ? (
              <><b>{nextFollow.title}</b><a href="#" onClick={(e) => { e.preventDefault(); seek(nextFollow.at); }}>{fmt(nextFollow.at)}부터 보기<Icon name="arrow" /></a></>
            ) : nextChapter ? (
              <><b>{nextChapter.title}</b><a href="#" onClick={(e) => { e.preventDefault(); seek(nextChapter.start); }}>{fmt(nextChapter.start)}부터 보기<Icon name="arrow" /></a></>
            ) : (
              <><b>공식 신청하기</b><a href={policy?.applyUrl ?? '#'} target="_blank" rel="noreferrer">신청 페이지로<Icon name="ext" /></a></>
            )}
          </div>
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
                {bigSub && subNow && <div className="cc"><span>“{subNow}”</span></div>}
              </div>
              <div className="ctl">
                <div className="tl" aria-label="장면 타임라인">
                  {shown.map((c, i) => (
                    <span key={c.id} className={`lab${c.id === current.id ? ' on' : ''}`} style={{ left: pct(c.start, total) }}>
                      {CIRCLED[i]} {c.short}
                    </span>
                  ))}
                  <div className="track" />
                  <div className="seg" style={{ left: pct(matched.start, total), width: pct(matched.end - matched.start, total) }} />
                  <div className="done" style={{ width: pct(time, total) }} />
                  {shown.map((c) => <span key={c.id} className="tick" style={{ left: pct(c.start, total) }} />)}
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
                  <button className="go" onClick={() => seek(c.start)}><Icon name="play" fill />{c.id === current.id ? '처음부터' : '여기부터'}</button>
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
                    <li key={s.step} className={state}>
                      <span className="d">{state === 'done' ? <Icon name="check" style={{ width: '.8rem', height: '.8rem' }} /> : s.step}</span>
                      <div>
                        <b>{s.title}{state === 'now' ? ' · 지금 보는 중' : ''}</b>
                        <small>
                          {s.videoAt !== undefined && <a href="#" onClick={(e) => { e.preventDefault(); seek(s.videoAt!); }}>영상 {fmt(s.videoAt)} </a>}
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
