import React, { useEffect, useState } from 'react';
import {
  Layers,
  ThumbsUp,
  ThumbsDown,
  MinusCircle,
  Star,
  Database,
  TrendingUp,
} from 'lucide-react';
import { OverviewAnalytics } from '../types/review';
import { getOverview } from '../services/api';
import { StatCard } from './StatCard';

export const DatasetOverview: React.FC = () => {
  const [overview, setOverview] = useState<OverviewAnalytics | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string>('');

  useEffect(() => {
    let isMounted = true;
    setLoading(true);
    getOverview()
      .then((data) => {
        if (isMounted) {
          setOverview(data);
          setError('');
        }
      })
      .catch((err) => {
        if (isMounted) {
          setError(
            err.response?.data?.detail ||
              'Dataset analytics could not be loaded. Please ensure the backend is running.'
          );
        }
      })
      .finally(() => {
        if (isMounted) setLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, []);

  if (loading) {
    return (
      <div className="rounded-2xl border border-white/10 bg-[#111827]/80 p-8 text-center space-y-3">
        <div className="inline-block h-8 w-8 animate-spin rounded-full border-2 border-purple-500 border-t-transparent" />
        <p className="text-xs text-slate-400 font-mono">Computing dataset analytics from CSV...</p>
      </div>
    );
  }

  if (error || !overview) {
    return (
      <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 p-6 text-center text-xs text-rose-300">
        <p className="font-semibold">{error || 'Unable to load dataset overview.'}</p>
      </div>
    );
  }

  const { total_reviews, average_rating, positive_reviews, neutral_reviews, negative_reviews, rating_distribution } =
    overview;

  const posPct = total_reviews > 0 ? ((positive_reviews / total_reviews) * 100).toFixed(1) : '0';
  const neuPct = total_reviews > 0 ? ((neutral_reviews / total_reviews) * 100).toFixed(1) : '0';
  const negPct = total_reviews > 0 ? ((negative_reviews / total_reviews) * 100).toFixed(1) : '0';

  return (
    <div className="space-y-6">
      {/* KPI Cards */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-bold uppercase tracking-wider text-slate-400 font-mono flex items-center gap-2">
            <Database className="h-4 w-4 text-cyan-400" />
            Dataset Benchmark Analytics
          </h2>
          <span className="text-xs text-slate-400 font-mono">
            Source: Kaggle Amazon Dataset ({total_reviews.toLocaleString()} records)
          </span>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3.5">
          <StatCard
            title="Total Records"
            value={total_reviews.toLocaleString()}
            icon={Layers}
            color="purple"
            subtitle="Verified CSV rows"
          />
          <StatCard
            title="Positive"
            value={positive_reviews.toLocaleString()}
            icon={ThumbsUp}
            color="emerald"
            subtitle={`${posPct}% (4-5 ★)`}
          />
          <StatCard
            title="Neutral"
            value={neutral_reviews.toLocaleString()}
            icon={MinusCircle}
            color="amber"
            subtitle={`${neuPct}% (3 ★)`}
          />
          <StatCard
            title="Negative"
            value={negative_reviews.toLocaleString()}
            icon={ThumbsDown}
            color="rose"
            subtitle={`${negPct}% (1-2 ★)`}
          />
          <StatCard
            title="Dataset Avg Rating"
            value={`${average_rating} ★`}
            icon={Star}
            color="cyan"
            subtitle="Ground Truth Mean"
          />
        </div>
      </div>

      {/* Distribution Section: Sentiment & Rating Breakdown */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        {/* Sentiment Distribution */}
        <div className="rounded-2xl border border-white/10 bg-[#111827]/80 p-5 backdrop-blur-xl space-y-4">
          <h3 className="text-sm font-bold text-white flex items-center gap-2">
            <TrendingUp className="h-4 w-4 text-emerald-400" />
            Sentiment Distribution (Dataset Ground Truth)
          </h3>
          <div className="space-y-3 pt-1">
            <div>
              <div className="flex justify-between text-xs font-medium mb-1 text-emerald-400">
                <span>Positive (4-5 Stars)</span>
                <span>
                  {positive_reviews.toLocaleString()} ({posPct}%)
                </span>
              </div>
              <div className="h-2.5 w-full rounded-full bg-slate-800 overflow-hidden">
                <div
                  className="h-full bg-emerald-500 rounded-full transition-all duration-500"
                  style={{ width: `${posPct}%` }}
                />
              </div>
            </div>

            <div>
              <div className="flex justify-between text-xs font-medium mb-1 text-amber-400">
                <span>Neutral (3 Stars)</span>
                <span>
                  {neutral_reviews.toLocaleString()} ({neuPct}%)
                </span>
              </div>
              <div className="h-2.5 w-full rounded-full bg-slate-800 overflow-hidden">
                <div
                  className="h-full bg-amber-500 rounded-full transition-all duration-500"
                  style={{ width: `${neuPct}%` }}
                />
              </div>
            </div>

            <div>
              <div className="flex justify-between text-xs font-medium mb-1 text-rose-400">
                <span>Negative (1-2 Stars)</span>
                <span>
                  {negative_reviews.toLocaleString()} ({negPct}%)
                </span>
              </div>
              <div className="h-2.5 w-full rounded-full bg-slate-800 overflow-hidden">
                <div
                  className="h-full bg-rose-500 rounded-full transition-all duration-500"
                  style={{ width: `${negPct}%` }}
                />
              </div>
            </div>
          </div>
        </div>

        {/* Rating Breakdown (1 to 5 Stars) */}
        <div className="rounded-2xl border border-white/10 bg-[#111827]/80 p-5 backdrop-blur-xl space-y-4">
          <h3 className="text-sm font-bold text-white flex items-center gap-2">
            <Star className="h-4 w-4 text-amber-400" />
            Rating Breakdown (1 to 5 Stars)
          </h3>
          <div className="space-y-2.5 pt-1">
            {[5, 4, 3, 2, 1].map((stars) => {
              const count = rating_distribution ? rating_distribution[stars] || 0 : 0;
              const pct = total_reviews > 0 ? ((count / total_reviews) * 100).toFixed(1) : '0';
              return (
                <div key={stars} className="flex items-center gap-3 text-xs">
                  <span className="w-12 font-mono font-medium text-amber-300 shrink-0">
                    {stars} Star{stars > 1 ? 's' : ''}
                  </span>
                  <div className="h-2 flex-1 rounded-full bg-slate-800 overflow-hidden">
                    <div
                      className="h-full bg-amber-400 rounded-full transition-all duration-500"
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                  <span className="w-20 text-right font-mono text-slate-400 shrink-0">
                    {count.toLocaleString()} ({pct}%)
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
};
