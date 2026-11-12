import { useEffect, useMemo, useState } from 'react';
import '../styles/watch.css';
import { Icon } from '../components/Icon';
import { SourceTag, VerifyBadge } from '../components/Common';
import { getVideo } from '../data/api';
import { basicPension, docs, officialSteps } from '../data/mock';
import type { VideoDetail } from '../data/types';
import { fmt, pct, won } from '../utils';

const CIRCLED = ['①', '②', '③', '④', '⑤', '⑥', '⑦', '⑧'];
const SPEEDS = [0.75, 1, 1.25];

export default function Watch({ videoId, startAt }: { videoId: string; startAt?: number }) {
  const [video, setVideo] = useState<VideoDetail | null>(null);
  const [time, setTime] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [repeat, setRepeat] = useState(true);
  const [bigSub, setBigSub] = useState(true);
  const [speed, setSpeed] = useState(1);
  const [checked, setChecked] = useState<Record<string, boolean>>({ id: true });

  useEffect(() => {
    getVideo(videoId).then((v) => {
      setVideo(v);
      const matched = v.chapters.find((c) => c.id === v.matchedChapterId);
      setTime(startAt ?? (matched ? matched.start + 65 : 0));
    });
  }, [videoId, startAt]);

  const chapters = video?.chapters ?? [];
  const current = useMemo(
    () => chapters.find((c) => time >= c.start && time < c.end) ?? chapters[chapters.length - 1],
    [chapters, time],
  );
  const matched = chapters.find((c) => c.id === video?.matchedChapterId);

  // 재생 흉내: 실제 영상(YouTube 등)을 붙이면 플레이어의 현재 시간으로 바꿔 주세요.
  useEffect(() => {
    if (!playing || !current || !video) return;
    const id = window.setInterval(() => {
      setTime((t) => {
        const next = t + speed;
        if (repeat && next >= current.end) return current.start;
        return Math.min(next, video.durationSec - 1);
      });
    }, 1000);
    return () => window.clearInterval(id);
  }, [playing, repeat, speed, current, video]);

  if (!video || !current || !matched) {
    return <main className="page-watch"><div className="wrap top"><p style={{ color: 'var(--muted)' }}>영상을 불러오고 있어요…</p></div></main>;
  }

  const total = video.durationSec;
  const isMatched = current.id === matched.id;
  const follow = current.follow ?? [];
  const followIdx = follow.reduce((acc, f, i) => (time >= f.at ? i : acc), 0);
  const nextFollow = follow[followIdx + 1];
  const nextChapter = chapters[chapters.indexOf(current) + 1];
  const prevChapter = chapters[chapters.indexOf(current) - 1];
  const seek = (t: number) => { setTime(t); setPlaying(true); };

  return (
    <main className="page-watch">
      <div className="wrap top">
        <div className="crumb"><span>홈</span>›<span>어르신 복지</span>›<span>기초연금</span>›<b>신청 안내 영상</b></div>
        <div className="th">
          <div>
            <div style={{ display: 'flex', gap: '.4rem', flexWrap: 'wrap' }}>
              <span className="tag tag-blue">기초연금</span><span className="tag tag-gray">자막 있음</span><span className="tag tag-gray">장면 {chapters.length}개</span>
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
          <span className="src src-gov"><Icon name="db" />정책정보</span><span>{basicPension.baseYear}년 기준 · 수정 {basicPension.updatedAt}</span>
        </div>

        {/* 지금 위치: 찾은 장면 / 지금 / 다음 */}
        <div className="where" aria-label="지금 위치">
          <div className="w1">
            <small><Icon name="search" />내가 찾은 장면</small>
            <b className="num">{fmt(matched.start)} – {fmt(matched.end)} · {matched.title.replace('복지로에서 ', '')}</b>
            <span>“{video.query}”</span>
          </div>
          <div className="w2">
            <small><Icon name="play" />지금 보는 단계</small>
            <b>{current.step ? `${current.step}단계` : current.stepLabel} · {follow[followIdx]?.title ?? current.title}</b>
            <span><VerifyBadge v={current.verification} long /></span>
          </div>
          <div className="w3">
            <small><Icon name="arrow" />다음에 할 일</small>
            {nextFollow ? (
              <><b>{nextFollow.title}</b><a href="#" onClick={(e) => { e.preventDefault(); seek(nextFollow.at); }}>{fmt(nextFollow.at)}부터 보기<Icon name="arrow" /></a></>
            ) : nextChapter ? (
              <><b>{nextChapter.title}</b><a href="#" onClick={(e) => { e.preventDefault(); seek(nextChapter.start); }}>{fmt(nextChapter.start)}부터 보기<Icon name="arrow" /></a></>
            ) : (
              <><b>복지로에서 공식 신청하기</b><a href={basicPension.applyUrl} target="_blank" rel="noreferrer">신청 페이지로<Icon name="ext" /></a></>
            )}
          </div>
        </div>

        <div className="grid">
          <div>
            {/* 플레이어 — 실제 영상은 여기에 YouTube iframe 등을 넣으면 돼요 */}
            <div className="player">
              <div className="stage">
                <div className="mon" aria-hidden="true">
                  <div className="bb"><i /><i /><i /><span>복지로 · 복지서비스 신청</span></div>
                  <div className="bd">
                    <div className="sd">{[0, 1, 2, 3, 4].map((i) => <i key={i} className={i === (current.step ?? 0) - 1 ? 'on' : ''} />)}</div>
                    <div className="mn">
                      <span className="h">{current.screenTitle}</span>
                      <div className="f"><i /><b /></div>
                      <div className="hlb"><div className="f"><i /><b /><i /><b /></div></div>
                    </div>
                  </div>
                </div>
                <div className="now">
                  <span><i />{isMatched ? `찾은 장면 재생 중 · ${fmt(matched.start)} – ${fmt(matched.end)}` : `재생 중 · ${current.title}`}</span>
                </div>
                {bigSub && <div className="cc"><span>“{current.subtitle}”</span></div>}
              </div>
              <div className="ctl">
                <div className="tl" aria-label="장면 타임라인">
                  {chapters.map((c, i) => (
                    <span key={c.id} className={`lab${c.id === current.id ? ' on' : ''}`} style={{ left: pct(c.start, total) }}>
                      {CIRCLED[i]} {c.short}
                    </span>
                  ))}
                  <div className="track" />
                  <div className="seg" style={{ left: pct(matched.start, total), width: pct(matched.end - matched.start, total) }} />
                  <div className="done" style={{ width: pct(time, total) }} />
                  {chapters.slice(1).map((c) => <span key={c.id} className="tick" style={{ left: pct(c.start, total) }} />)}
                  <span className="head" style={{ left: pct(time, total) }} />
                </div>
                <div className="cb">
                  <button className="pp" aria-label={playing ? '일시정지' : '재생'} onClick={() => setPlaying(!playing)}>
                    <Icon name={playing ? 'pause' : 'play'} fill={!playing} />
                  </button>
                  <button onClick={() => setTime(Math.max(0, time - 10))}><Icon name="rew" />10초 뒤로</button>
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
              {chapters.map((c) => (
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

          {/* 오른쪽 공식 정책정보 */}
          <aside className="card pp-card" aria-label="공식 정책정보">
            <div className="hd">
              <div className="r1"><SourceTag kind="gov" /><span style={{ fontSize: '.8rem', color: 'var(--muted)' }}>{basicPension.baseYear}년 기준</span></div>
              <h2>{basicPension.name}</h2>
              <p>출처 {basicPension.source} · 수정 {basicPension.updatedAt}</p>
            </div>
            <div className="blk"><h3><span className="n">1</span>받을 수 있는 분</h3>
              <p>만 65세 이상이고, 소득인정액이 혼자 <b>{basicPension.incomeLimit.single}</b>, 부부 <b>{basicPension.incomeLimit.couple}</b> 이하인 분</p></div>
            <div className="blk"><h3><span className="n">2</span>받는 금액</h3>
              <div className="money"><span>혼자 사는 경우 최대</span><b className="num">월 {won(basicPension.maxAmount.single)}원</b></div>
              <div className="money" style={{ marginTop: '.1rem' }}><span>부부 최대</span><b className="num" style={{ fontSize: '1.1rem', color: 'var(--ink)' }}>월 {won(basicPension.maxAmount.couple)}원</b></div></div>
            <div className="blk"><details>
              <summary><span className="n">3</span>신청 시기<span className="r">{basicPension.applyWhen}<Icon name="chev" /></span></summary>
              <p>예: 1961년 4월생은 2026년 3월 1일부터 신청할 수 있어요.</p>
            </details></div>
            <div className="blk"><h3><span className="n">4</span>준비 서류 확인</h3>
              <div className="docs">
                {docs.slice(0, 3).map((d) => (
                  <label key={d.id} className={current.relatedDocs.includes(d.id) ? 'rel' : ''}>
                    <input type="checkbox" checked={!!checked[d.id]} onChange={(e) => setChecked({ ...checked, [d.id]: e.target.checked })} />
                    <span>{d.name}</span>
                    {current.relatedDocs.includes(d.id) && <span className="tag tag-blue">이 장면</span>}
                  </label>
                ))}
              </div>
              <p className="note">준비 여부를 확인하는 용도예요. 자격을 판정하지 않아요.</p></div>
            <div className="blk"><h3><span className="n">5</span>공식 신청 단계</h3>
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
                          {s.videoAt !== undefined && s.verification === 'screen' && <>영상 {fmt(s.videoAt)} </>}
                          {s.verification === 'subtitle' && <span className="vb vb-sub" style={{ fontSize: '.72rem', padding: '0 .4rem' }}>자막만</span>}
                          {s.verification === 'none' && <span className="vb vb-none" style={{ fontSize: '.72rem', padding: '0 .4rem' }}>해당 장면 없음</span>}
                          {s.verification !== 'screen' && s.note}
                        </small>
                      </div>
                    </li>
                  );
                })}
              </ol></div>
            <div className="blk"><details>
              <summary><Icon name="alert" style={{ color: 'var(--amber)' }} />신청 전 꼭 확인<span className="r">2가지<Icon name="chev" /></span></summary>
              <p>부부가 함께 신청하면 배우자 본인 인증도 필요해요. 가족이 대신 신청하면 위임장이 있어야 해요.</p>
            </details></div>
            <div className="cta">
              <a className="btn btn-pri btn-lg btn-block" href={basicPension.applyUrl} target="_blank" rel="noreferrer">복지로에서 공식 신청하기<Icon name="ext" /></a>
              <div className="two">
                <a className="btn btn-line" href="#"><Icon name="pin" />주민센터 찾기</a>
                <a className="btn btn-line" href="tel:129"><Icon name="phone" />129 상담</a>
              </div>
              <a className="btn btn-soft btn-block" href="#" style={{ marginTop: '.5rem' }}><Icon name="print" />신청서·동의서 서식 받기 (HWP·PDF)</a>
              <p>신청은 복지로에서 이뤄져요. 복지바로봄은 개인정보를 받지 않아요.</p>
            </div>
          </aside>
        </div>
      </div>
    </main>
  );
}
