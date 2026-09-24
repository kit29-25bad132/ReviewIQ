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
      <div className="relative overflow-hidden rounded-2xl border border-purple-500/30 bg-[#111827]/90 p-6 sm:p-7 backdrop-blur-xl shadow-glass">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div className="space-y-2">
            <div className="flex flex-wrap items-center gap-2.5">
              <span className="rounded-full bg-indigo-500/20 border border-indigo-500/30 px-3 py-0.5 text-xs font-semibold text-indigo-300">
                {product.category || 'General Category'}
              </span>
              <span className="rounded-full bg-slate-800 border border-slate-700 px-3 py-0.5 text-xs font-mono text-slate-300">
                Product ID: {product.product_id}
              </span>
            </div>

            <h2 className="text-xl sm:text-2xl font-black tracking-tight text-white">
              {product.product_title}
            </h2>

            <p className="text-xs text-slate-400 flex items-center gap-1.5 font-mono">
              <Database className="h-3.5 w-3.5 text-cyan-400" />
              <span>Source: ReviewIQ Product Review Dataset ({review_count.toLocaleString()} actual reviews)</span>
            </p>
          </div>

          {/* Big Score Card */}
          <div className="flex items-center gap-4 rounded-2xl border border-slate-800 bg-[#0B0F17]/90 p-4 sm:p-5 shrink-0">
            <div className="text-center">
              <div className="text-3xl sm:text-4xl font-black font-mono text-amber-400 flex items-center justify-center gap-1">
                <span>{average_rating.toFixed(2)}</span>
                <Star className="h-6 w-6 fill-amber-400 text-amber-400" />
              </div>
              <div className="text-[11px] font-mono text-slate-400 mt-1">Average Rating</div>
            </div>

            <div className="h-10 w-px bg-slate-800" />

            <div className="text-center">
              <div className="text-2xl sm:text-3xl font-black font-mono text-white">
                {review_count.toLocaleString()}
              </div>
              <div className="text-[11px] font-mono text-slate-400 mt-1">Verified Reviews</div>
            </div>
          </div>
        </div>
      </div>

      {/* Breakdown Grid: Rating Distribution & Sentiment Analysis */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Rating Distribution (5★ to 1★) */}
        <div className="rounded-2xl border border-white/10 bg-[#111827]/80 p-6 backdrop-blur-xl shadow-glass space-y-4">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <h3 className="text-sm font-bold text-white flex items-center gap-2">
              <BarChart3 className="h-4 w-4 text-amber-400" />
              Rating Distribution
            </h3>
            <span className="text-[11px] font-mono text-slate-400">1 to 5 Stars</span>
          </div>

          <div className="space-y-3">
            {['5', '4', '3', '2', '1'].map((star) => {
              const count = rating_distribution[star] || 0;
              const pct = ((count / totalReviews) * 100).toFixed(1);
              return (
                <div key={star} className="flex items-center gap-3 text-xs">
                  <div className="flex items-center gap-1 w-14 font-mono font-bold text-amber-300 shrink-0">
                    <span>{star}</span>
                    <Star className="h-3 w-3 fill-amber-400" />
                  </div>

                  <div className="h-2.5 flex-1 rounded-full bg-slate-800 overflow-hidden">
                    <div
                      className="h-full bg-amber-400 rounded-full transition-all duration-500"
                      style={{ width: `${pct}%` }}
                    />
                  </div>

                  <div className="w-24 text-right font-mono text-slate-300 shrink-0">
                    <span>{count.toLocaleString()}</span>{' '}
                    <span className="text-slate-500 text-[10px]">({pct}%)</span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Sentiment Analysis Breakdown */}
        <div className="rounded-2xl border border-white/10 bg-[#111827]/80 p-6 backdrop-blur-xl shadow-glass space-y-4">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <h3 className="text-sm font-bold text-white flex items-center gap-2">
              <TrendingUp className="h-4 w-4 text-emerald-400" />
              Sentiment Analysis
            </h3>
            <span className="text-[11px] font-mono text-slate-400">Ground-Truth Classification</span>
          </div>

          <div className="space-y-4 pt-1">
            {/* Positive */}
            <div>
              <div className="flex justify-between text-xs font-semibold mb-1 text-emerald-400">
                <span className="flex items-center gap-1.5">
                  <ThumbsUp className="h-3.5 w-3.5" /> Positive Sentiment
                </span>
                <span className="font-mono">
                  {posCount.toLocaleString()} ({posPct}%)
                </span>
              </div>
              <div className="h-2.5 w-full rounded-full bg-slate-800 overflow-hidden">
                <div
                  className="h-full bg-emerald-500 rounded-full transition-all duration-500"
                  style={{ width: `${posPct}%` }}
                />
              </div>
            </div>

            {/* Neutral */}
            <div>
              <div className="flex justify-between text-xs font-semibold mb-1 text-amber-400">
                <span className="flex items-center gap-1.5">
                  <MinusCircle className="h-3.5 w-3.5" /> Neutral Sentiment
                </span>
                <span className="font-mono">
                  {neuCount.toLocaleString()} ({neuPct}%)
                </span>
              </div>
              <div className="h-2.5 w-full rounded-full bg-slate-800 overflow-hidden">
                <div
                  className="h-full bg-amber-500 rounded-full transition-all duration-500"
                  style={{ width: `${neuPct}%` }}
                />
              </div>
            </div>

            {/* Negative */}
            <div>
              <div className="flex justify-between text-xs font-semibold mb-1 text-rose-400">
                <span className="flex items-center gap-1.5">
                  <ThumbsDown className="h-3.5 w-3.5" /> Negative Sentiment
                </span>
                <span className="font-mono">
                  {negCount.toLocaleString()} ({negPct}%)
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
      </div>
    </div>
  );
};
