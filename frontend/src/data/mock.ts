// 시연용 가짜 데이터 — 금액·날짜·영상 시간은 예시예요.
// 백엔드가 준비되면 src/data/api.ts 에서 실제 API로 바꿔 주세요.
import type { Chapter, DocItem, OfficialStep, Policy, SceneResult, VideoDetail } from './types';

export const basicPension: Policy = {
  policyId: 'basic-pension',
  name: '기초연금',
  category: '노후 소득 보장',
  target: '만 65세 이상',
  targetDetail: '만 65세 이상이고 소득인정액이 선정기준액 이하인 분',
  criteria: '소득인정액이 혼자 월 247만원, 부부 월 395.2만원 이하',
  benefit: '단독가구 최고 349,700원, 부부가구 최고 559,520원',
  applyMethod: '복지로 온라인 · 주민센터 방문',
  applyWhen: '65세 생일 달 1개월 전부터',
  requiredDocs: ['신분증', '본인 통장 사본', '금융정보 제공 동의서'],
  contact: '보건복지상담센터/129',
  agency: '보건복지부',
  applyUrl: 'https://www.bokjiro.go.kr',
  officialUrls: [],
  amount: [{ label: '혼자 사는 경우 최대(월)', value: '349,700원' }, { label: '부부 최대(월)', value: '559,520원' }],
  source: '한국사회보장정보원 복지서비스정보 Open API',
  baseYear: 2026,
  updatedAt: '[YYYY.MM.DD]',
};

export const docs: DocItem[] = [
  { id: 'id', name: '신분증' },
  { id: 'bank', name: '본인 통장 사본' },
  { id: 'consent', name: '금융정보 제공 동의서', note: '배우자가 있으면 배우자도' },
  { id: 'lease', name: '임대차계약서', note: '전세·월세인 경우만' },
];

export const sceneResults: SceneResult[] = [
  {
    videoId: 'v1',
    title: '기초연금 신청 안내 — 자격부터 복지로 온라인 신청까지',
    publisher: '[게시기관]',
    publishedAt: '[YYYY.MM.DD]',
    duration: '14:20',
    thumbType: 'screen',
    found: { start: 515, end: 680, label: '복지로 신청서 작성 화면', verification: 'screen' },
    otherScenes: [
      { start: 105, label: '받을 수 있는지' },
      { start: 270, label: '준비 서류' },
    ],
  },
  {
    videoId: 'v2',
    title: '휴대폰으로 기초연금 신청하기',
    publisher: '[게시기관]',
    publishedAt: '[YYYY.MM.DD]',
    duration: '09:45',
    thumbType: 'phone',
    found: { start: 195, end: 340, label: '휴대폰 신청서 입력', verification: 'screen' },
  },
  {
    videoId: 'v3',
    title: '기초연금 자주 묻는 질문',
    publisher: '[게시기관]',
    publishedAt: '[YYYY.MM.DD]',
    duration: '11:10',
    thumbType: 'paper',
    found: { start: 435, end: 470, label: '신청서 작성 방법을 말로 설명', verification: 'subtitle' },
  },
];

const chapters: Chapter[] = [
  {
    id: 'c0', short: '도입', start: 0, end: 105, title: '2026년 달라진 점', step: null, stepLabel: '도입',
    verification: 'none', subtitle: '올해 달라진 기초연금 기준을 먼저 알아볼게요.',
    screenTitle: '2026년 기초연금 안내', relatedDocs: [],
  },
  {
    id: 'c1', short: '자격', start: 105, end: 270, title: '받을 수 있는지 확인하기', step: 1, stepLabel: '1단계',
    verification: 'screen', subtitle: '모의계산 화면에서 소득과 재산을 입력해 보세요.',
    screenTitle: '소득인정액 모의계산', relatedDocs: [],
    follow: [
      { title: '모의계산 화면 열기', desc: '복지로에서 ‘모의계산’을 눌러요.', at: 105 },
      { title: '소득·재산 입력하기', desc: '한 달 소득과 재산을 대략 적어요.', at: 160 },
      { title: '결과 확인하기', desc: '받을 수 있을지 예상 결과를 봐요.', at: 230 },
    ],
  },
  {
    id: 'c2', short: '서류', start: 270, end: 515, title: '준비 서류 챙기기', step: 2, stepLabel: '2단계',
    verification: 'screen', subtitle: '신분증과 본인 명의 통장 사본을 준비해 주세요.',
    screenTitle: '제출 서류 안내', relatedDocs: ['id', 'bank', 'consent'],
    follow: [
      { title: '신분증 준비하기', desc: '주민등록증이나 운전면허증을 챙겨요.', at: 270 },
      { title: '통장 사본 준비하기', desc: '연금을 받을 본인 통장이에요.', at: 330 },
      { title: '동의서 확인하기', desc: '배우자가 있으면 배우자도 서명해요.', at: 420 },
    ],
  },
  {
    id: 'c3', short: '신청서 작성', start: 515, end: 680, title: '복지로에서 신청서 쓰기', step: 3, stepLabel: '3단계',
    verification: 'screen', subtitle: '서비스 목록에서 기초연금을 선택하세요.',
    screenTitle: '신청할 서비스 선택', relatedDocs: ['bank', 'consent'],
    follow: [
      { title: '복지로에 로그인하기', desc: '간편인증이나 공동인증서로 본인 확인을 해요.', at: 515 },
      { title: '신청할 서비스 고르기', desc: '‘복지서비스 신청’에서 기초연금을 선택해요.', at: 560 },
      { title: '신청서 쓰고 서류 제출하기', desc: '가족·통장 정보를 적고 동의서에 서명한 뒤 제출해요.', at: 605 },
    ],
  },
  {
    id: 'c4', short: '결과', start: 680, end: 860, title: '결과 확인과 첫 지급', step: 4, stepLabel: '4단계',
    verification: 'subtitle', subtitle: '심사 결과는 문자나 우편으로 알려드려요.',
    screenTitle: '결과 안내', relatedDocs: [],
  },
];

export const videoDetail: VideoDetail = {
  videoId: 'v1',
  title: '기초연금 신청 안내 — 자격부터 복지로 온라인 신청까지',
  publisher: '[게시기관]',
  publishedAt: '[YYYY.MM.DD]',
  durationSec: 860,
  query: '기초연금 신청서 어떻게 써요?',
  matchedChapterId: 'c3',
  chapters,
  policy: null,
  docs: [],
  officialSteps: [],
};

export const officialSteps: OfficialStep[] = [
  { step: 1, title: '받을 수 있는지 확인', note: '모의계산으로 미리 확인', videoAt: 105, verification: 'screen' },
  { step: 2, title: '서류 준비', note: '신분증, 통장, 동의서', videoAt: 270, verification: 'screen' },
  { step: 3, title: '신청서 작성·제출', note: '복지로 온라인 또는 주민센터', videoAt: 515, verification: 'screen' },
  { step: 4, title: '소득·재산 조사, 결과 안내', note: '문자·우편으로 안내', videoAt: 680, verification: 'subtitle' },
  { step: 5, title: '매월 25일 지급', note: '공식 안내 보기', verification: 'none' },
];

videoDetail.policy = basicPension;
videoDetail.docs = docs;
videoDetail.officialSteps = officialSteps;

// 시연 영상 세트에서 고른 장면 (backend/data/demo_videos.json, 시간은 시연 질문 시험 결과)
export const popularScenes = [
  { policy: '기초연금', videoId: 'KBBwdz4sidM', title: '기초연금 신청, 이렇게 하면된다!', duration: '04:38', thumbType: 'screen' as const,
    scenes: [{ t: 114, label: '신청 서류 보기', hit: true }, { t: 44, label: '신청 기간 이야기' }] },
  { policy: '기초연금', videoId: 'NYNnaDN9d8M', title: '기초연금 온라인 신청, 홈페이지 편', duration: '10:01', thumbType: 'screen' as const,
    scenes: [{ t: 77, label: '서비스 목록에서 기초연금 선택', hit: true }, { t: 0, label: '온라인 신청 안내' }] },
  { policy: '청년월세 지원', videoId: 'ibeZ6H7CO9U', title: '청년 월세 특별지원 안내', duration: '08:40', thumbType: 'paper' as const,
    scenes: [{ t: 445, label: '제출 서류', hit: true }, { t: 120, label: '지원 금액' }] },
  { policy: '아이돌봄서비스', videoId: 'SfKD_WW0qQY', title: '서울시 아이돌봄 서비스 신청 과정', duration: '06:28', thumbType: 'phone' as const,
    scenes: [{ t: 15, label: '어디서 신청하나요', hit: true }, { t: 152, label: '홈페이지 가입' }] },
];

export const audienceGroups = [
  {
    label: '나이로',
    items: [
      { icon: 'elder', title: '어르신', tag: '65세 이상', policies: ['기초연금', '노인맞춤돌봄', '노인일자리'] },
      { icon: 'cap', title: '청년', tag: '19~34세', policies: ['청년월세 지원', '청년도약계좌', '취업지원'] },
      { icon: 'family', title: '가족·육아', tag: '임신·육아', policies: ['부모급여', '아이돌봄', '첫만남이용권'] },
      { icon: 'wheel', title: '장애인·취약계층', tag: '생계·의료·돌봄', policies: ['장애인연금', '활동지원', '긴급복지'] },
    ],
  },
  {
    label: '가구 상황으로',
    items: [
      { icon: 'family', title: '한부모·조손', tag: '혼자 자녀 양육', policies: ['아동양육비', '교육급여'] },
      { icon: 'wheel', title: '장애인 가구', tag: '본인·가족', policies: ['장애인연금', '활동지원'] },
      { icon: 'family', title: '다문화 가구', tag: '결혼이민자', policies: ['다문화가족 지원'] },
      { icon: 'elder', title: '저소득 가구', tag: '생활이 어려울 때', policies: ['생계급여', '주거급여', '긴급복지'] },
    ],
  },
  {
    label: '필요한 것으로',
    items: [
      { icon: 'elder', title: '집·주거', tag: '월세·전세', policies: ['청년월세 지원', '주거급여'] },
      { icon: 'cap', title: '일자리', tag: '취업 준비', policies: ['국민취업지원제도'] },
      { icon: 'wheel', title: '건강·의료', tag: '병원비', policies: ['재난적의료비'] },
      { icon: 'family', title: '돌봄·보육', tag: '아이·어르신', policies: ['아이돌봄', '노인맞춤돌봄'] },
    ],
  },
];
