import React from 'react';
import { LucideIcon } from 'lucide-react';

interface StatCardProps {
  title: string;
  value: string | number;
  icon: LucideIcon;
  color: 'purple' | 'emerald' | 'rose' | 'amber' | 'cyan';
  subtitle?: string;
}

const colorStyles = {
  purple: {
    bg: 'from-purple-500/10 to-transparent',
    border: 'border-purple-500/20 hover:border-purple-500/40',
    iconBg: 'bg-purple-500/15 text-purple-400',
    glow: 'group-hover:shadow-[0_0_20px_rgba(139,92,246,0.25)]',
    text: 'text-purple-400',
  },
  emerald: {
    bg: 'from-emerald-500/10 to-transparent',
    border: 'border-emerald-500/20 hover:border-emerald-500/40',
    iconBg: 'bg-emerald-500/15 text-emerald-400',
    glow: 'group-hover:shadow-[0_0_20px_rgba(16,185,129,0.25)]',
    text: 'text-emerald-400',
  },
  rose: {
    bg: 'from-rose-500/10 to-transparent',
    border: 'border-rose-500/20 hover:border-rose-500/40',
    iconBg: 'bg-rose-500/15 text-rose-400',
    glow: 'group-hover:shadow-[0_0_20px_rgba(244,63,94,0.25)]',
    text: 'text-rose-400',
  },
  amber: {
    bg: 'from-amber-500/10 to-transparent',
    border: 'border-amber-500/20 hover:border-amber-500/40',
    iconBg: 'bg-amber-500/15 text-amber-400',
    glow: 'group-hover:shadow-[0_0_20px_rgba(245,158,11,0.25)]',
    text: 'text-amber-400',
  },
  cyan: {
    bg: 'from-cyan-500/10 to-transparent',
    border: 'border-cyan-500/20 hover:border-cyan-500/40',
    iconBg: 'bg-cyan-500/15 text-cyan-400',
    glow: 'group-hover:shadow-[0_0_20px_rgba(6,182,212,0.25)]',
    text: 'text-cyan-400',
  },
};

export const StatCard: React.FC<StatCardProps> = ({
  title,
  value,
  icon: Icon,
  color,
  subtitle,
}) => {
  const style = colorStyles[color];

  return (
    <div
      className={`group relative overflow-hidden rounded-2xl border bg-gradient-to-b bg-[#111827]/80 p-5 backdrop-blur-xl transition-all duration-300 ${style.bg} ${style.border} ${style.glow}`}
    >
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
          {title}
        </span>
        <div className={`flex h-10 w-10 items-center justify-center rounded-xl ${style.iconBg}`}>
          <Icon className="h-5 w-5" />
        </div>
      </div>
      <div className="mt-3 flex items-baseline gap-2">
        <span className="text-2xl sm:text-3xl font-bold tracking-tight text-white font-mono">
          {value}
        </span>
        {subtitle && (
          <span className="text-xs text-slate-400 font-medium">{subtitle}</span>
        )}
      </div>
    </div>
  );
};
