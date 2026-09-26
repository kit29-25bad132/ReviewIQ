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
      <div className="premium-panel p-6 sm:p-8 relative overflow-hidden">
        <div className="absolute right-0 top-0 h-40 w-40 rounded-bl-full border-b border-l border-[#D4AF5A]/10 pointer-events-none" />

        <div className="flex flex-col md:flex-row md:items-center justify-between gap-6 relative">
          <div className="space-y-3 max-w-2xl">
            <div className="flex flex-wrap items-center gap-2.5">
              <span className="rounded-full border border-[#D4AF5A]/30 bg-[#1B1915] px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.15em] text-[#D4AF5A]">
                {product.category || 'General Category'}
              </span>
              <span className="rounded-full border border-[#292A2B] bg-[#151617] px-3 py-1 text-xs font-mono text-[#74736E]">
                ASIN / ID: {product.product_id}
              </span>
            </div>

            <h2 className="text-2xl sm:text-3xl font-medium tracking-[-0.03em] text-[#F5F2EA]">
              {product.product_title}
            </h2>

            <p className="text-xs text-[#AAA79F] flex items-center gap-2">
              <Database className="h-3.5 w-3.5 text-[#D4AF5A]" />
              <span>Real Review Dataset ({review_count.toLocaleString()} actual customer reviews analyzed)</span>
            </p>
          </div>

          {/* Big Score Card */}
          <div className="flex items-center gap-6 rounded-xl border border-[#292A2B] bg-[#151617] p-5 shrink-0 shadow-lg">
            <div className="text-center">
              <div className="text-3xl sm:text-4xl font-semibold text-[#D4AF5A] flex items-center justify-center gap-1.5">
                <span>{average_rating.toFixed(1)}</span>
                <span className="text-base text-[#74736E]">/ 5</span>
              </div>
              <div className="text-[11px] uppercase tracking-wider text-[#74736E] mt-1">Average Rating</div>
            </div>

            <div className="h-10 w-px bg-[#292A2B]" />

            <div className="text-center">
              <div className="text-2xl sm:text-3xl font-semibold text-[#F5F2EA]">
                {review_count.toLocaleString()}
              </div>
              <div className="text-[11px] uppercase tracking-wider text-[#74736E] mt-1">Total Reviews</div>
            </div>
          </div>
        </div>
      </div>

      {/* Breakdown Grid: Rating Distribution & Sentiment Analysis */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Rating Distribution (5★ to 1★) */}
        <div className="premium-panel p-6 space-y-4">
          <div className="flex items-center justify-between border-b border-[#292A2B] pb-3">
            <h3 className="text-sm font-medium text-[#F5F2EA] flex items-center gap-2">
              <BarChart3 className="h-4 w-4 text-[#D4AF5A]" />
              Rating Distribution
            </h3>
            <span className="text-xs text-[#74736E]">1 to 5 Stars</span>
          </div>

          <div className="space-y-3">
            {['5', '4', '3', '2', '1'].map((star) => {
              const count = rating_distribution[star] || 0;
              const pct = ((count / totalReviews) * 100).toFixed(1);
              return (
                <div key={star} className="flex items-center gap-3 text-xs">
                  <div className="flex items-center gap-1 w-12 font-medium text-[#D4AF5A] shrink-0">
                    <span>{star}</span>
                    <Star className="h-3 w-3 fill-[#D4AF5A]" />
                  </div>

                  <div className="relative h-2 flex-1 rounded-full bg-[#292A2B] overflow-hidden">
                    <div
                      className="h-full rounded-full bg-gradient-to-r from-[#D4AF5A] to-[#B98B28] transition-all duration-500"
                      style={{ width: `${pct}%` }}
                    />
                  </div>

                  <div className="w-20 text-right font-mono text-[#AAA79F] shrink-0">
                    {count.toLocaleString()} ({pct}%)
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Sentiment Analysis Distribution */}
        <div className="premium-panel p-6 space-y-4">
          <div className="flex items-center justify-between border-b border-[#292A2B] pb-3">
            <h3 className="text-sm font-medium text-[#F5F2EA] flex items-center gap-2">
              <TrendingUp className="h-4 w-4 text-[#D4AF5A]" />
              Sentiment Breakdown
            </h3>
            <span className="text-xs text-[#74736E]">Evidence Based</span>
          </div>

          <div className="space-y-3">
            {/* Positive */}
            <div className="flex items-center justify-between rounded-lg border border-[#292A2B] bg-[#151617] p-3 text-xs">
              <div className="flex items-center gap-2 text-emerald-400 font-medium">
                <ThumbsUp className="h-4 w-4" />
                <span>Positive Reviews</span>
              </div>
              <div className="flex items-center gap-3">
                <span className="font-mono text-[#F5F2EA]">{posCount.toLocaleString()}</span>
                <span className="rounded bg-emerald-950/60 border border-emerald-800/40 px-2 py-0.5 font-mono text-emerald-400">
                  {posPct}%
                </span>
              </div>
            </div>

            {/* Neutral */}
            <div className="flex items-center justify-between rounded-lg border border-[#292A2B] bg-[#151617] p-3 text-xs">
              <div className="flex items-center gap-2 text-[#D4AF5A] font-medium">
                <MinusCircle className="h-4 w-4" />
                <span>Neutral Reviews</span>
              </div>
              <div className="flex items-center gap-3">
                <span className="font-mono text-[#F5F2EA]">{neuCount.toLocaleString()}</span>
                <span className="rounded bg-amber-950/60 border border-amber-800/40 px-2 py-0.5 font-mono text-[#D4AF5A]">
                  {neuPct}%
                </span>
              </div>
            </div>

            {/* Negative */}
            <div className="flex items-center justify-between rounded-lg border border-[#292A2B] bg-[#151617] p-3 text-xs">
              <div className="flex items-center gap-2 text-rose-400 font-medium">
                <ThumbsDown className="h-4 w-4" />
                <span>Negative Reviews</span>
              </div>
              <div className="flex items-center gap-3">
                <span className="font-mono text-[#F5F2EA]">{negCount.toLocaleString()}</span>
                <span className="rounded bg-rose-950/60 border border-rose-800/40 px-2 py-0.5 font-mono text-rose-400">
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
