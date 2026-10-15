import React from 'react';
import {
  AlertTriangle,
  CheckCircle2,
  CircleDashed,
  Clock3,
  LoaderCircle,
  SearchX,
} from 'lucide-react';
import { CardAnalysisStatus } from '../types';

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
}

export const AnalysisStatusBadge: React.FC<AnalysisStatusBadgeProps> = ({
  status,
  reason,
}) => {
  const { label, className, Icon } = BADGE_STYLES[status];

  return (
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
};
