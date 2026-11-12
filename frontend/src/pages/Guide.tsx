import '../styles/guide.css';
import { Icon, type IconName } from '../components/Icon';
import { SourceTag, VerifyBadge } from '../components/Common';

const FEATURES: { icon: IconName | '가'; title: string; desc: string; where: string }[] = [
  { icon: '가', title: '글자 크기', desc: '보통·크게·아주 크게 중에서 골라요.', where: '맨 위 바' },
  { icon: 'contrast', title: '고대비', desc: '글자와 배경의 차이를 더 크게 해요.', where: '맨 위 바' },
  { icon: 'speaker', title: '화면 읽어주기', desc: '화면의 글을 소리로 읽어줘요.', where: '맨 위 바' },
  { icon: 'text', title: '큰 자막', desc: '영상 자막을 크게 보여줘요.', where: '영상 아래' },
  { icon: 'repeat', title: '이 장면 반복', desc: '찾은 장면만 계속 다시 재생해요.', where: '영상 아래' },
  { icon: 'mic', title: '말로 묻기', desc: '타자 대신 말로 질문해요.', where: '검색창' },
];

const FAQ = [
  { q: '여기서 바로 신청이 되나요?', a: '아니요. 복지바로봄은 정보와 영상을 보여드리고, 신청은 복지로·정부24·주민센터에서 해요.' },
  { q: '개인정보를 입력해야 하나요?', a: '아니요. 주민등록번호 같은 개인정보는 받지 않아요.' },
  { q: '이용료가 있나요?', a: '무료예요. 정부 지원금 신청에 돈을 요구하면 사기이니 129에 알려주세요.' },
  { q: '모의계산 결과대로 받을 수 있나요?', a: '예상일 뿐이에요. 실제로 받을 수 있는지는 주민센터 심사로 정해져요.' },
  { q: '찾는 영상이 없으면요?', a: '공식 안내 글로 신청 방법을 보여드려요. 전화 상담도 이용할 수 있어요.' },
];

export default function Guide() {
  const jump = (id: string) => document.getElementById(id)?.scrollIntoView({ behavior: 'smooth' });
  return (
    <main className="page-guide">
      <section className="gh"><div className="wrap">
        <div>
          <div className="eyebrow">이용 안내</div>
          <h1>복지바로봄, 이렇게 쓰세요</h1>
          <p>궁금한 복지를 물어보면 공식 정보와 영상 속 장면을 함께 보여드려요.</p>
        </div>
        <nav className="toc" aria-label="이 페이지 목차">
          {[['s1', '사용 순서'], ['s2', '표시 읽는 법'], ['s3', '편의 기능'], ['s4', '정보 출처'], ['s5', '자주 묻는 질문']].map(([id, label]) => (
            <button key={id} className="chip" onClick={() => jump(id)}>{label}</button>
          ))}
        </nav>
      </div></section>

      <div className="wrap">
        <section className="section" id="s1">
          <div className="blockh"><span className="no">01</span><h2>사용 순서</h2><p>세 단계면 신청 페이지까지 갈 수 있어요.</p></div>
          <div className="flow3">
            <div className="card c"><div className="k"><b>1</b><h3>말하듯 물어보기</h3></div><p>정책 이름을 몰라도 돼요. 글이나 말로 물어보세요.</p>
              <div className="mini" aria-hidden="true"><div className="sb"><Icon name="search" />기초연금 신청서 어떻게 써요?</div></div></div>
            <div className="card c"><div className="k"><b>2</b><h3>찾은 장면 보기</h3></div><p>AI가 찾은 장면부터 재생돼요. 시간을 눌러 다른 장면으로도 갈 수 있어요.</p>
              <div className="mini" aria-hidden="true"><div className="fb"><span style={{ fontWeight: 800, color: 'var(--blue-dark)', fontSize: '.75rem' }}>AI가 찾은 장면</span><br /><b className="num">08:35 – 11:20</b> 신청서 작성</div></div></div>
            <div className="card c"><div className="k"><b>3</b><h3>공식 사이트에서 신청</h3></div><p>준비가 끝나면 복지로·정부24 신청 화면으로 이동해요.</p>
              <div className="mini" aria-hidden="true"><span className="go">복지로에서 공식 신청하기<Icon name="ext" /></span></div></div>
          </div>
        </section>

        <section className="section" id="s2">
          <div className="blockh"><span className="no">02</span><h2>화면 표시 읽는 법</h2><p>색과 함께 글자로도 구분해 두었어요.</p></div>
          <div className="legend">
            <div className="card c"><h3>영상 장면 상태</h3>
              <div className="lg"><VerifyBadge v="screen" /><p>신청 화면이 영상에 실제로 나와요.</p></div>
              <div className="lg"><VerifyBadge v="subtitle" /><p>말로만 설명하고 화면은 나오지 않아요.</p></div>
              <div className="lg"><VerifyBadge v="none" long /><p>영상에 없는 단계예요. 공식 안내 글을 봐 주세요.</p></div>
            </div>
            <div className="card c"><h3>정보 출처</h3>
              <div className="lg"><SourceTag kind="gov" /><p>공공데이터에서 가져온 금액·대상·기간이에요.</p></div>
              <div className="lg"><SourceTag kind="ai" /><p>영상의 자막과 화면을 분석한 결과예요. 참고용이에요.</p></div>
              <div className="lg"><span className="tag tag-dark">재생 중</span><p>지금 보고 있는 장면과 신청 단계예요.</p></div>
            </div>
          </div>
        </section>

        <section className="section" id="s3">
          <div className="blockh"><span className="no">03</span><h2>편하게 보는 기능</h2><p>보기 어려우면 아래 기능을 켜 보세요.</p></div>
          <div className="feat">
            {FEATURES.map((f) => (
              <div key={f.title} className="card c">
                <span className="ic" style={f.icon === '가' ? { fontWeight: 800 } : undefined}>{f.icon === '가' ? '가' : <Icon name={f.icon} />}</span>
                <div><b>{f.title}</b><p>{f.desc}</p><span className="where">{f.where}</span></div>
              </div>
            ))}
          </div>
        </section>

        <section className="section" id="s4">
          <div className="blockh"><span className="no">04</span><h2>정보 출처와 기준일</h2><p>모든 정책 화면에 출처와 기준일을 표시해요.</p></div>
          <div className="card data">
            <table>
              <thead><tr><th>정보</th><th>어디서 오나요</th><th>표시 방법</th></tr></thead>
              <tbody>
                <tr><td><span className="src src-gov">공식 정책정보</span></td><td>행정안전부 공공서비스(혜택) 정보, 한국사회보장정보원 복지서비스정보 Open API</td><td>기준연도와 최종 수정일</td></tr>
                <tr><td><span className="src src-ai">AI 영상 분석</span></td><td>공공기관이 공개한 안내 영상 중 이용 권한을 확보한 영상</td><td>게시기관, 게시일, 검증 상태</td></tr>
                <tr><td><b>신청</b></td><td>복지로·정부24·주민센터</td><td>공식 사이트로 이동</td></tr>
              </tbody>
            </table>
            <div className="limit"><Icon name="info" /><span>AI가 찾은 장면과 검증 상태는 틀릴 수 있어요. 영상과 공식 정보가 다르면 <b>공식 정보를 먼저</b> 따라 주세요. 장면이 맞지 않으면 영상 화면의 ‘알려주기’를 눌러 주세요.</span></div>
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
              <a className="tel" href="tel:129"><span><small>보건복지상담센터 · 24시간</small><b>국번 없이 129</b></span><span className="c"><Icon name="phone" /></span></a>
              <a className="tel" href="tel:1355"><span><small>국민연금공단</small><b>1355</b></span><span className="c"><Icon name="phone" /></span></a>
              <a className="tel" href="tel:107"><span><small>손말이음센터 · 청각·언어 장애인</small><b>107</b></span><span className="c"><Icon name="phone" /></span></a>
              <a className="btn btn-line btn-block" href="#"><Icon name="pin" />가까운 주민센터 찾기</a>
            </aside>
          </div>
        </section>
      </div>
    </main>
  );
}
