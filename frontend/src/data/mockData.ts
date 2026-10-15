import { VideoMetadata, SearchResponse } from '../types';

export const MOCK_VIDEOS: Record<string, VideoMetadata> = {
  'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11': {
    video_id: 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11',
    title: 'AirPods Pro 2세대 심층 분석 및 실사용 배터리 테스트 리포트',
    category: 'tech',
    categoryLabel: '제품 리뷰',
    channelName: '테크랩 스튜디오',
    publishDate: '2024.04.18',
    views: '18.2만회',
    thumbnailUrl: 'https://images.unsplash.com/photo-1600294037681-c80b4cb5b434?auto=format&fit=crop&w=800&q=80',
    videoUrl: 'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4',
    totalDuration: 990, // 16:30
    chapters: [
      { timestamp: 135, title: '외관 디자인 및 포트' },
      { timestamp: 522, title: '배터리 지속 시간 및 무선 충전' },
      { timestamp: 760, title: '노이즈 캔슬링 실측 비교' },
      { timestamp: 910, title: '통화 품질 테스트' }
    ]
  },
  xyz789: {
    video_id: 'xyz789',
    title: '정밀 피펫으로 시작하는 화학 용액 분주 정밀 실험',
    category: 'education',
    categoryLabel: '교육 · 실험',
    channelName: '과학 실험실 + 랩 리포트',
    publishDate: '2024.03.12',
    views: '9.4만회',
    thumbnailUrl: 'https://images.unsplash.com/photo-1582719478250-c89cae4dc85b?auto=format&fit=crop&w=800&q=80',
    videoUrl: 'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ElephantsDream.mp4',
    totalDuration: 630, // 10:30
    chapters: [
      { timestamp: 45, title: '실험 도구 준비 및 멸균 과정' },
      { timestamp: 150, title: '용액 농도 측정 및 시약 혼합' },
      { timestamp: 390, title: '정밀 피펫 용액 분주 시연' },
      { timestamp: 540, title: '반응 결과 분석 및 오차 검토' }
    ]
  },
  vlog456: {
    video_id: 'vlog456',
    title: '햇살 드는 거실의 원목 도어 손잡이를 여는 장면 - 공간 투어',
    category: 'vlog',
    categoryLabel: '일상 · 브이로그',
    channelName: '일상 브이로그 + 인테리어',
    publishDate: '2024.05.02',
    views: '14.1만회',
    thumbnailUrl: 'https://images.unsplash.com/photo-1600585154340-be6161a56a0c?auto=format&fit=crop&w=800&q=80',
    videoUrl: 'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4',
    totalDuration: 750, // 12:30
    chapters: [
      { timestamp: 60, title: '모닝 루틴과 채광 체크' },
      { timestamp: 210, title: '원목 도어와 입구 동선' },
      { timestamp: 420, title: '미니멀 가구 배치와 조명' },
      { timestamp: 650, title: '오후 티타임과 마무리' }
    ]
  },
  sport101: {
    video_id: 'sport101',
    title: '추가시간 극장골 성공 후 슬라이딩 환호 세레머니 명장면',
    category: 'sports',
    categoryLabel: '스포츠 경기',
    channelName: '스포츠 하이라이트 · 축구',
    publishDate: '2024.02.27',
    views: '42.8만회',
    thumbnailUrl: 'https://images.unsplash.com/photo-1508098682722-e99c43a406b2?auto=format&fit=crop&w=800&q=80',
    videoUrl: 'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/TearsOfSteel.mp4',
    totalDuration: 520, // 08:40
    chapters: [
      { timestamp: 90, title: '전반전 치열한 중원 압박' },
      { timestamp: 240, title: '후반 80분 결정적 유효 슈팅' },
      { timestamp: 410, title: '극장골 터진 직후 슬라이딩 세레머니' },
      { timestamp: 490, title: '관중석 환호 및 인터뷰' }
    ]
  }
};

/**
 * Pre-defined mock query responses matching user intent
 */
export const DEFAULT_SEARCH_RESPONSES: Record<string, SearchResponse> = {
  '에어팟 프로 2 배터리를 설명하는 부분': {
    query: '에어팟 프로 2 배터리를 설명하는 부분',
    results: [
      {
        video_id: 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11',
        segment_id: 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11_seg_021',
        start_time: 203.4, // 03:23
        end_time: 241.7,   // 04:01
        score: 0.96
      },
      {
        video_id: 'xyz789',
        segment_id: 'xyz789_seg_008',
        start_time: 78.2,  // 01:18
        end_time: 109.4,  // 01:49
        score: 0.93
      },
      {
        video_id: 'vlog456',
        segment_id: 'vlog456_seg_014',
        start_time: 132.0, // 02:12
        end_time: 170.0, // 02:50
        score: 0.91
      },
      {
        video_id: 'sport101',
        segment_id: 'sport101_seg_033',
        start_time: 165.0, // 02:45
        end_time: 210.0, // 03:30
        score: 0.88
      }
    ]
  },
  '제품의 배터리를 설명하는 부분': {
    query: '제품의 배터리를 설명하는 부분',
    results: [
      {
        video_id: 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11',
        segment_id: 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11_seg_021',
        start_time: 203.4,
        end_time: 241.7,
        score: 0.96
      },
      {
        video_id: 'xyz789',
        segment_id: 'xyz789_seg_008',
        start_time: 78.2,
        end_time: 109.4,
        score: 0.85
      },
      {
        video_id: 'vlog456',
        segment_id: 'vlog456_seg_014',
        start_time: 132.0,
        end_time: 170.0,
        score: 0.76
      }
    ]
  },
  '피아노치는 장면': {
    query: '피아노치는 장면',
    results: [
      {
        video_id: 'xyz789',
        segment_id: 'xyz789_seg_008',
        start_time: 78.2,
        end_time: 109.4,
        score: 0.97
      },
      {
        video_id: 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11',
        segment_id: 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11_seg_004',
        start_time: 45.0,
        end_time: 82.0,
        score: 0.82
      },
      {
        video_id: 'vlog456',
        segment_id: 'vlog456_seg_002',
        start_time: 60.0,
        end_time: 95.0,
        score: 0.74
      }
    ]
  },
  '경기에서 골이 들어가는 순간': {
    query: '경기에서 골이 들어가는 순간',
    results: [
      {
        video_id: 'sport101',
        segment_id: 'sport101_seg_033',
        start_time: 165.0,
        end_time: 210.0,
        score: 0.98
      },
      {
        video_id: 'vlog456',
        segment_id: 'vlog456_seg_014',
        start_time: 132.0,
        end_time: 170.0,
        score: 0.81
      },
      {
        video_id: 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11',
        segment_id: 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11_seg_021',
        start_time: 203.4,
        end_time: 241.7,
        score: 0.72
      }
    ]
  },
  '사람이 문을 여는 장면': {
    query: '사람이 문을 여는 장면',
    results: [
      {
        video_id: 'vlog456',
        segment_id: 'vlog456_seg_014',
        start_time: 132.0,
        end_time: 170.0,
        score: 0.95
      },
      {
        video_id: 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11',
        segment_id: 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11_seg_021',
        start_time: 203.4,
        end_time: 241.7,
        score: 0.84
      },
      {
        video_id: 'xyz789',
        segment_id: 'xyz789_seg_008',
        start_time: 78.2,
        end_time: 109.4,
        score: 0.79
      }
    ]
  },
  '에어팟 프로2 배터리를 설명하는 부분': {
    query: '에어팟 프로2 배터리를 설명하는 부분',
    results: [
      {
        video_id: 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11',
        segment_id: 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11_seg_021',
        start_time: 203.4,
        end_time: 241.7,
        score: 0.96
      },
      {
        video_id: 'xyz789',
        segment_id: 'xyz789_seg_008',
        start_time: 78.2,
        end_time: 109.4,
        score: 0.93
      },
      {
        video_id: 'vlog456',
        segment_id: 'vlog456_seg_014',
        start_time: 132.0,
        end_time: 170.0,
        score: 0.91
      },
      {
        video_id: 'sport101',
        segment_id: 'sport101_seg_033',
        start_time: 165.0,
        end_time: 210.0,
        score: 0.88
      }
    ]
  },
  '피펫으로 용액을 옮기는 장면': {
    query: '피펫으로 용액을 옮기는 장면',
    results: [
      {
        video_id: 'xyz789',
        segment_id: 'xyz789_seg_008',
        start_time: 78.2,
        end_time: 109.4,
        score: 0.97
      },
      {
        video_id: 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11',
        segment_id: 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11_seg_004',
        start_time: 45.0,
        end_time: 82.0,
        score: 0.85
      },
      {
        video_id: 'vlog456',
        segment_id: 'vlog456_seg_002',
        start_time: 60.0,
        end_time: 95.0,
        score: 0.76
      }
    ]
  },
  '선수가 골을 넣는 장면': {
    query: '선수가 골을 넣는 장면',
    results: [
      {
        video_id: 'sport101',
        segment_id: 'sport101_seg_033',
        start_time: 165.0,
        end_time: 210.0,
        score: 0.98
      },
      {
        video_id: 'vlog456',
        segment_id: 'vlog456_seg_014',
        start_time: 132.0,
        end_time: 170.0,
        score: 0.82
      },
      {
        video_id: 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11',
        segment_id: 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11_seg_021',
        start_time: 203.4,
        end_time: 241.7,
        score: 0.74
      }
    ]
  },
  '방을 꾸미는 장면': {
    query: '방을 꾸미는 장면',
    results: [
      {
        video_id: 'vlog456',
        segment_id: 'vlog456_seg_014',
        start_time: 132.0,
        end_time: 170.0,
        score: 0.96
      },
      {
        video_id: 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11',
        segment_id: 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11_seg_021',
        start_time: 203.4,
        end_time: 241.7,
        score: 0.86
      },
      {
        video_id: 'xyz789',
        segment_id: 'xyz789_seg_008',
        start_time: 78.2,
        end_time: 109.4,
        score: 0.80
      }
    ]
  }
};

export const RECOMMENDED_QUERIES = [
  '에어팟 프로2 배터리를 설명하는 부분',
  '피아노치는 장면',
  '선수가 골을 넣는 장면',
  '방을 꾸미는 장면'
];

export const SHOWCASE_VIDEOS = [
  {
    videoId: 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11',
    category: '제품 리뷰',
    categoryBadgeClass: 'bg-blue-600/90 text-white',
    categoryIcon: 'Laptop',
    title: '에어팟 프로 2 배터리 수명 및 실사용 테스트',
    thumbnailUrl: 'https://images.unsplash.com/photo-1600294037681-c80b4cb5b434?auto=format&fit=crop&w=800&q=80',
    query: '에어팟 프로 2 배터리를 설명하는 부분'
  },
  {
    videoId: 'xyz789',
    category: '교육 · 실험',
    categoryBadgeClass: 'bg-blue-600/90 text-white',
    categoryIcon: 'FlaskConical',
    title: '마이크로 피펫 용액 분주 화학 정밀 실험',
    thumbnailUrl: 'https://images.unsplash.com/photo-1582719478250-c89cae4dc85b?auto=format&fit=crop&w=800&q=80',
    query: '실험에서 용액을 옮기는 장면'
  },
  {
    videoId: 'vlog456',
    category: '일상 · 브이로그',
    categoryBadgeClass: 'bg-blue-600/90 text-white',
    categoryIcon: 'Home',
    title: '따스한 자연광 원목 인테리어 공간 투어',
    thumbnailUrl: 'https://images.unsplash.com/photo-1600585154340-be6161a56a0c?auto=format&fit=crop&w=800&q=80',
    query: '사람이 문을 여는 장면'
  },
  {
    videoId: 'sport101',
    category: '스포츠 경기',
    categoryBadgeClass: 'bg-blue-600/90 text-white',
    categoryIcon: 'Trophy',
    title: '후반 극장골 결정적 세레머니 명장면',
    thumbnailUrl: 'https://images.unsplash.com/photo-1508098682722-e99c43a406b2?auto=format&fit=crop&w=800&q=80',
    query: '경기에서 골이 들어가는 순간'
  }
];
