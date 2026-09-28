import React from 'react';
import {
  Star,
  ThumbsUp,
  ThumbsDown,
  MinusCircle,
  Database,
  BarChart3,
  TrendingUp,
} from 'lucide-react';
import { ProductAnalysisResponse } from '../types/ecommerce';

interface ProductOverviewProps {
  analysis: ProductAnalysisResponse;
}

export const ProductOverview: React.FC<ProductOverviewProps> = ({ analysis }) => {
  const { product, statistics } = analysis;
  const { review_count, average_rating, rating_distribution, sentiment_distribution } = statistics;

  const totalReviews = review_count || 1;

  const posCount = sentiment_distribution['positive'] || 0;
  const neuCount = sentiment_distribution['neutral'] || 0;
  const negCount = sentiment_distribution['negative'] || 0;

  const posPct = ((posCount / totalReviews) * 100).toFixed(1);
  const neuPct = ((neuCount / totalReviews) * 100).toFixed(1);
  const negPct = ((negCount / totalReviews) * 100).toFixed(1);

  return (
    <div className="space-y-6">
      {/* Main Product Hero Card */}
      <div className="modern-card p-6 sm:p-8 relative overflow-hidden bg-gradient-to-br from-white via-white to-indigo-50/30">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-6 relative">
          <div className="space-y-3 max-w-2xl">
            <div className="flex flex-wrap items-center gap-2.5">
              <span className="rounded-full bg-indigo-50 border border-indigo-100 px-3 py-1 text-[11px] font-semibold text-indigo-700">
                {product.category || 'General Category'}
              </span>
              <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-mono text-slate-500">
                ID: {product.product_id}
              </span>
            </div>

            <h2 className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-900">
              {product.product_title}
            </h2>

            <p className="text-xs text-slate-500 flex items-center gap-2">
              <Database className="h-3.5 w-3.5 text-indigo-600" />
              <span>Verified Dataset Intelligence ({review_count.toLocaleString()} customer reviews analyzed)</span>
            </p>
          </div>

          {/* Big Score Card */}
          <div className="flex items-center gap-6 rounded-2xl border border-slate-200/90 bg-white p-5 shrink-0 shadow-sm">
            <div className="text-center">
              <div className="text-3xl sm:text-4xl font-extrabold text-amber-500 flex items-center justify-center gap-1.5">
                <span>{average_rating.toFixed(1)}</span>
                <span className="text-sm font-medium text-slate-400">/ 5</span>
              </div>
              <div className="text-[11px] font-medium text-slate-500 mt-1">Average Rating</div>
            </div>

            <div className="h-10 w-px bg-slate-200" />

            <div className="text-center">
              <div className="text-2xl sm:text-3xl font-extrabold text-slate-800">
                {review_count.toLocaleString()}
              </div>
              <div className="text-[11px] font-medium text-slate-500 mt-1">Total Reviews</div>
            </div>
          </div>
        </div>
      </div>

      {/* Breakdown Grid: Rating Distribution & Sentiment Analysis */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Rating Distribution (5★ to 1★) */}
        <div className="modern-card p-6 space-y-4">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3">
            <h3 className="text-sm font-semibold text-slate-800 flex items-center gap-2">
              <BarChart3 className="h-4 w-4 text-indigo-600" />
              Rating Distribution
            </h3>
            <span className="text-xs text-slate-400">1 to 5 Stars</span>
          </div>

          <div className="space-y-3">
            {['5', '4', '3', '2', '1'].map((star) => {
              const count = rating_distribution[star] || 0;
              const pct = ((count / totalReviews) * 100).toFixed(1);
              return (
                <div key={star} className="flex items-center gap-3 text-xs">
                  <div className="flex items-center gap-1 w-12 font-semibold text-amber-500 shrink-0">
                    <span>{star}</span>
                    <Star className="h-3 w-3 fill-amber-400 text-amber-400" />
                  </div>

                  <div className="h-2.5 flex-1 rounded-full bg-slate-100 overflow-hidden">
                    <div
                      className="h-full rounded-full bg-amber-400 transition-all duration-700 ease-out"
                      style={{ width: `${pct}%` }}
                    />
                  </div>

                  <div className="w-16 text-right font-mono text-slate-500 shrink-0">
                    <span>{count}</span>
                    <span className="text-[10px] text-slate-400 ml-1">({pct}%)</span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Sentiment Breakdown */}
        <div className="modern-card p-6 space-y-4">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3">
            <h3 className="text-sm font-semibold text-slate-800 flex items-center gap-2">
              <TrendingUp className="h-4 w-4 text-emerald-600" />
              Sentiment Breakdown
            </h3>
            <span className="text-xs text-slate-400">Evidence Based</span>
          </div>

          <div className="space-y-3 pt-1">
            {/* Positive */}
            <div className="flex items-center justify-between rounded-xl bg-emerald-50/80 border border-emerald-100 p-3">
              <div className="flex items-center gap-2.5">
                <ThumbsUp className="h-4 w-4 text-emerald-600" />
                <span className="text-xs font-semibold text-emerald-900">Positive Reviews</span>
              </div>
              <div className="flex items-center gap-3 font-mono text-xs">
                <span className="text-emerald-800 font-bold">{posCount}</span>
                <span className="rounded-md bg-emerald-100 px-2 py-0.5 text-[11px] font-semibold text-emerald-700">
                  {posPct}%
                </span>
              </div>
            </div>

            {/* Neutral */}
            <div className="flex items-center justify-between rounded-xl bg-amber-50/80 border border-amber-100 p-3">
              <div className="flex items-center gap-2.5">
                <MinusCircle className="h-4 w-4 text-amber-600" />
                <span className="text-xs font-semibold text-amber-900">Neutral Reviews</span>
              </div>
              <div className="flex items-center gap-3 font-mono text-xs">
                <span className="text-amber-800 font-bold">{neuCount}</span>
                <span className="rounded-md bg-amber-100 px-2 py-0.5 text-[11px] font-semibold text-amber-700">
                  {neuPct}%
                </span>
              </div>
            </div>

            {/* Negative */}
            <div className="flex items-center justify-between rounded-xl bg-rose-50/80 border border-rose-100 p-3">
              <div className="flex items-center gap-2.5">
                <ThumbsDown className="h-4 w-4 text-rose-600" />
                <span className="text-xs font-semibold text-rose-900">Negative Reviews</span>
              </div>
              <div className="flex items-center gap-3 font-mono text-xs">
                <span className="text-rose-800 font-bold">{negCount}</span>
                <span className="rounded-md bg-rose-100 px-2 py-0.5 text-[11px] font-semibold text-rose-700">
                  {negPct}%
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
