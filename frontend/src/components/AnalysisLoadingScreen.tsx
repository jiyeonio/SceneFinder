import React from 'react';
import { LoaderCircle } from 'lucide-react';

// 기존 검색 결과 화면(VideoSearchListView)의 "AI 영상 분석 중..." 로딩 박스를
// 여러 흐름에서 함께 쓰도록 분리한 컴포넌트입니다. (마크업/스타일은 기존 그대로)
interface AnalysisLoadingScreenProps {
  title: React.ReactNode;
  description?: React.ReactNode;
  // 기본은 회전하는 로딩 아이콘. 실패 안내 등에서는 다른 아이콘을 넘깁니다.
  icon?: React.ReactNode;
  // 상태 배지, 버튼 등 추가 내용
  children?: React.ReactNode;
}

export const AnalysisLoadingScreen: React.FC<AnalysisLoadingScreenProps> = ({
  title,
  description,
  icon,
  children,
}) => (
  <div
    role="status"
    data-testid="analysis-loading-screen"
    className="flex min-h-[380px] flex-col items-center justify-center rounded-2xl border border-slate-200 bg-white p-8 text-center"
  >
    {icon ?? (
      <LoaderCircle className="mb-5 h-12 w-12 animate-spin text-blue-600" />
    )}

    <h2 className="text-lg font-bold text-slate-900">{title}</h2>

    {description && (
      <p className="mt-3 text-sm leading-relaxed text-slate-500">
        {description}
      </p>
    )}

    {children}
  </div>
);
