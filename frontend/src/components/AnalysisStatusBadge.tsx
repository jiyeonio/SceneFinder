import React from 'react';
import {
  AlertTriangle,
  CheckCircle2,
  CircleDashed,
  Clock3,
  LoaderCircle,
  SearchX,
} from 'lucide-react';
import { CaptionStatus, CardAnalysisStatus } from '../types';

const BADGE_STYLES: Record<
  CardAnalysisStatus,
  { label: string; className: string; Icon: React.ElementType }
> = {
  checking: {
    label: '확인 중',
    className: 'bg-slate-50 text-slate-400',
    Icon: Clock3,
  },
  idle: {
    label: '분석 전',
    className: 'border border-slate-200 bg-white text-slate-500',
    Icon: CircleDashed,
  },
  queued: {
    label: '분석 대기',
    className: 'bg-slate-100 text-slate-600',
    Icon: Clock3,
  },
  analyzing: {
    label: '분석 중',
    className: 'bg-blue-50 text-blue-700',
    Icon: LoaderCircle,
  },
  done: {
    label: '완료',
    className: 'bg-emerald-50 text-emerald-700',
    Icon: CheckCircle2,
  },
  no_results: {
    label: '결과 없음',
    className: 'bg-amber-50 text-amber-700',
    Icon: SearchX,
  },
  failed: {
    label: '실패',
    className: 'bg-red-50 text-red-700',
    Icon: AlertTriangle,
  },
};

interface AnalysisStatusBadgeProps {
  status: CardAnalysisStatus;
  reason?: string;
  // 분석 완료 후 화면 설명(설명문) 상태. 만드는 중/대기 중일 때만 따로 표시
  captionStatus?: CaptionStatus;
}

const CAPTION_LABELS: Partial<Record<CaptionStatus, string>> = {
  PROCESSING: '화면 분석 중',
  PENDING: '화면 분석 대기',
};

export const AnalysisStatusBadge: React.FC<AnalysisStatusBadgeProps> = ({
  status,
  reason,
  captionStatus,
}) => {
  const { label, className, Icon } = BADGE_STYLES[status];
  const captionLabel =
    status === 'done' || status === 'no_results'
      ? captionStatus && CAPTION_LABELS[captionStatus]
      : undefined;

  const badge = (
    <span
      data-status={status}
      title={reason}
      className={`inline-flex shrink-0 items-center gap-1 rounded-full px-2.5 py-1 text-xs font-semibold ${className}`}
    >
      <Icon
        className={`h-3.5 w-3.5 ${status === 'analyzing' ? 'animate-spin' : ''}`}
      />
      {label}
      {reason && <span className="font-medium">· {reason}</span>}
    </span>
  );

  if (!captionLabel) return badge;

  // 자막 검색은 이미 되고, 화면 설명이 끝나면 결과가 더 좋아질 수 있음을 알림
  return (
    <span className="inline-flex shrink-0 flex-wrap items-center justify-end gap-1">
      {badge}
      <span
        data-caption-status={captionStatus}
        title="자막으로 먼저 검색했어요. 화면 설명이 끝나면 화면에만 보이는 장면도 찾아요."
        className="inline-flex items-center gap-1 rounded-full bg-violet-50 px-2.5 py-1 text-xs font-semibold text-violet-700"
      >
        {captionStatus === 'PROCESSING' ? (
          <LoaderCircle className="h-3.5 w-3.5 animate-spin" />
        ) : (
          <Clock3 className="h-3.5 w-3.5" />
        )}
        {captionLabel}
      </span>
    </span>
  );
};
