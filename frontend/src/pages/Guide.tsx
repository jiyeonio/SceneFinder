import '../styles/guide.css';
import { Icon, type IconName } from '../components/Icon';
import { SourceTag, VerifyBadge } from '../components/Common';

const FEATURES: { icon: IconName | '가'; title: string; desc: string; where: string }[] = [
  { icon: '가', title: '글자 크기', desc: '3단계로 조절', where: '맨 위 바' },
  { icon: 'contrast', title: '고대비', desc: '더 선명하게', where: '맨 위 바' },
  { icon: 'speaker', title: '화면 읽어주기', desc: '소리로 듣기', where: '맨 위 바' },
  { icon: 'text', title: '큰 자막', desc: '자막 크게', where: '영상 아래' },
  { icon: 'repeat', title: '이 장면 반복', desc: '찾은 장면만 반복', where: '영상 아래' },
  { icon: 'mic', title: '말로 묻기', desc: '말로 검색', where: '검색창' },
];

const FAQ = [
  { q: '여기서 바로 신청이 되나요?', a: '아니요. 신청은 복지로·정부24·주민센터에서 해요.' },
  { q: '개인정보를 입력해야 하나요?', a: '아니요. 받지 않아요.' },
  { q: '이용료가 있나요?', a: '무료예요. 돈을 요구하면 사기예요.' },
  { q: '금액·기간은 무엇을 기준으로 해요?', a: '공공데이터 공식 정보예요. 수정일도 함께 보여줘요.' },
  { q: '찾는 영상이 없으면요?', a: '공식 안내 글로 보여드려요.' },
];

export default function Guide() {
  const jump = (id: string) => document.getElementById(id)?.scrollIntoView({ behavior: 'smooth' });
  return (
    <main className="page-guide">
      <section className="gh sg-band"><div className="wrap">
        <div>
          <h1 className="sg-title">복지바로봄, 이렇게 쓰세요</h1>
          <div className="sg-meta"><span>3단계면 끝나요</span></div>
        </div>
      </div></section>

      <div className="wrap sg-gl">
        <aside className="sg-toc sticky" aria-label="이 페이지 목차">
          {[['s1', '사용 순서'], ['s2', '표시 읽는 법'], ['s3', '편의 기능'], ['s4', '정보 출처'], ['s5', '자주 묻는 질문']].map(([id, label], i) => (
            <a key={id} href={`#${id}`} aria-current={i === 0 ? 'true' : undefined} onClick={(e) => { e.preventDefault(); jump(id); }}><b>{i + 1}</b>{label}</a>
          ))}
        </aside>
        <div className="sg-gmain">
        <section className="section" id="s1">
          <div className="blockh"><span className="no">01</span><h2>사용 순서</h2></div>
          <div className="flow3">
            <div className="card c"><div className="k"><b>1</b><h3>말하듯 물어보기</h3></div>
              <div className="mini" aria-hidden="true"><div className="sb"><Icon name="search" />기초연금 신청서 어떻게 써요?</div></div></div>
            <div className="card c"><div className="k"><b>2</b><h3>찾은 장면 보기</h3></div>
              <div className="mini" aria-hidden="true"><div className="fb"><span style={{ fontWeight: 800, color: 'var(--blue-dark)', fontSize: '.75rem' }}>AI가 찾은 장면</span><br /><b className="num">08:35 – 11:20</b> 신청서 작성</div></div></div>
            <div className="card c"><div className="k"><b>3</b><h3>공식 사이트 신청</h3></div>
              <div className="mini" aria-hidden="true"><span className="go">복지로에서 공식 신청하기<Icon name="ext" /></span></div></div>
          </div>
        </section>

        <section className="section" id="s2">
          <div className="blockh"><span className="no">02</span><h2>화면 표시 읽는 법</h2></div>
          <div className="legend">
            <div className="card c"><h3>영상 장면 상태</h3>
              <div className="lg"><VerifyBadge v="screen" /><p>신청 화면이 나와요.</p></div>
              <div className="lg"><VerifyBadge v="subtitle" /><p>말로만 설명해요.</p></div>
              <div className="lg"><VerifyBadge v="pending" /><p>몇 초 뒤 바뀌어요.</p></div>
              <div className="lg"><VerifyBadge v="none" /><p>공식 정보를 봐 주세요.</p></div>
            </div>
            <div className="card c"><h3>정보 출처</h3>
              <div className="lg"><SourceTag kind="gov" /><p>공공데이터 기준이에요.</p></div>
              <div className="lg"><SourceTag kind="ai" /><p>참고용이에요.</p></div>
              <div className="lg"><span className="tag tag-dark">재생 중</span><p>지금 보는 장면이에요.</p></div>
            </div>
          </div>
        </section>

        <section className="section" id="s3">
          <div className="blockh"><span className="no">03</span><h2>편하게 보는 기능</h2></div>
          <div className="feat">
            {FEATURES.map((f) => (
              <div key={f.title} className="card c">
                <span className="ic" style={f.icon === '가' ? { fontWeight: 800 } : undefined}>{f.icon === '가' ? '가' : <Icon name={f.icon} />}</span>
                <div><b>{f.title}</b><span className="where">{f.where}</span></div>
              </div>
            ))}
          </div>
        </section>

        <section className="section" id="s4">
          <div className="blockh"><span className="no">04</span><h2>정보 출처와 기준일</h2></div>
          <div className="card data">
            <table>
              <thead><tr><th>정보</th><th>어디서 오나요</th></tr></thead>
              <tbody>
                <tr><td><span className="src src-gov">공식 정책정보</span></td><td>사회보장 공공데이터 (기준일 표시)</td></tr>
                <tr><td><span className="src src-ai">AI 영상 분석</span></td><td>공공기관 안내 영상</td></tr>
                <tr><td><b>신청</b></td><td>복지로·정부24·주민센터</td></tr>
              </tbody>
            </table>
            <div className="limit"><Icon name="info" /><span>AI 결과는 틀릴 수 있어요. 다르면 <b>공식 정보</b>를 따라 주세요.</span></div>
          </div>
        </section>

        <section className="section" id="s5">
          <div className="blockh"><span className="no">05</span><h2>자주 묻는 질문</h2></div>
          <div className="two">
            <div className="card faq">
              {FAQ.map((f, i) => <details key={f.q} open={i === 0}><summary>{f.q}</summary><p>{f.a}</p></details>)}
            </div>
            <aside className="card help">
              <h3>도움이 필요하세요?</h3>
              <a className="tel" href="tel:129"><span><small>보건복지상담센터</small><b>국번 없이 129</b></span><span className="c"><Icon name="phone" /></span></a>
              <a className="tel" href="tel:1355"><span><small>국민연금공단</small><b>1355</b></span><span className="c"><Icon name="phone" /></span></a>
              <a className="tel" href="tel:107"><span><small>손말이음센터</small><b>107</b></span><span className="c"><Icon name="phone" /></span></a>
              <a className="btn btn-line btn-block" href="#"><Icon name="pin" />가까운 주민센터 찾기</a>
            </aside>
          </div>
        </section>
        </div>
      </div>
    </main>
  );
}
