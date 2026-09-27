import React from 'react';
import { Smile, Meh, Frown, Star, BarChart2 } from 'lucide-react';
import { ProductStatistics } from '../types/ecommerce';

interface SentimentOverviewProps {
  statistics: ProductStatistics;
  sentimentPercentages?: Record<string, number>;
}

export const SentimentOverview: React.FC<SentimentOverviewProps> = ({
  statistics,
  sentimentPercentages,
}) => {
  const sentimentCounts = statistics.sentiment_distribution || {};
  const posCount = sentimentCounts.positive || 0;
  const neuCount = sentimentCounts.neutral || 0;
  const negCount = sentimentCounts.negative || 0;
  const totalSentiment = posCount + neuCount + negCount || 1;

  const posPct =
    sentimentPercentages?.positive !== undefined
      ? sentimentPercentages.positive
      : Math.round((posCount / totalSentiment) * 100);

  const neuPct =
    sentimentPercentages?.neutral !== undefined
      ? sentimentPercentages.neutral
      : Math.round((neuCount / totalSentiment) * 100);

  const negPct =
    sentimentPercentages?.negative !== undefined
      ? sentimentPercentages.negative
      : Math.max(0, 100 - posPct - neuPct);

  // Rating distribution 1 to 5
  const ratingDist = statistics.rating_distribution || {};
  const totalRatings =
    Object.values(ratingDist).reduce((sum, count) => sum + count, 0) || statistics.review_count || 1;

  return (
    <div className="grid gap-4 sm:grid-cols-1 lg:grid-cols-2">
      {/* Sentiment Breakdown Card */}
      <div className="premium-panel p-6 border border-[#292A2B] bg-[#151617]">
        <div className="mb-5 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="flex h-7 w-7 items-center justify-center rounded-md border border-[#292A2B] bg-[#1C1D1F] text-[#D4AF5A]">
              <BarChart2 className="h-4 w-4" />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-[#F5F2EA]">Sentiment Breakdown</h3>
              <p className="text-[11px] text-[#74736E]">Categorized by natural language analysis</p>
            </div>
          </div>
          <span className="text-xs font-mono text-[#AAA79F]">
            {totalSentiment.toLocaleString()} reviews analyzed
          </span>
        </div>

        {/* Multi-segment Progress Bar */}
        <div className="mb-6 flex h-3 w-full overflow-hidden rounded-full bg-[#1C1D1F] p-0.5 border border-[#292A2B]">
          <div
            style={{ width: `${posPct}%` }}
            className="h-full rounded-l-full bg-emerald-500 transition-all duration-500"
            title={`Positive: ${posPct}%`}
          />
          <div
            style={{ width: `${neuPct}%` }}
            className="h-full bg-amber-500 transition-all duration-500"
            title={`Neutral: ${neuPct}%`}
          />
          <div
            style={{ width: `${negPct}%` }}
            className="h-full rounded-r-full bg-rose-500 transition-all duration-500"
            title={`Negative: ${negPct}%`}
          />
        </div>

        {/* Sentiment Metrics Grid */}
        <div className="grid grid-cols-3 gap-2">
          {/* Positive */}
          <div className="rounded-lg border border-[#292A2B] bg-[#18191B] p-3 text-center">
            <div className="flex items-center justify-center gap-1.5 text-xs font-medium text-emerald-400 mb-1">
              <Smile className="h-3.5 w-3.5" />
              <span>Positive</span>
            </div>
            <p className="text-xl font-bold text-[#F5F2EA]">{posPct.toFixed(1)}%</p>
            <p className="text-[10px] text-[#74736E] mt-0.5">{posCount.toLocaleString()} reviews</p>
          </div>

          {/* Neutral */}
          <div className="rounded-lg border border-[#292A2B] bg-[#18191B] p-3 text-center">
            <div className="flex items-center justify-center gap-1.5 text-xs font-medium text-amber-400 mb-1">
              <Meh className="h-3.5 w-3.5" />
              <span>Neutral</span>
            </div>
            <p className="text-xl font-bold text-[#F5F2EA]">{neuPct.toFixed(1)}%</p>
            <p className="text-[10px] text-[#74736E] mt-0.5">{neuCount.toLocaleString()} reviews</p>
          </div>

          {/* Negative */}
          <div className="rounded-lg border border-[#292A2B] bg-[#18191B] p-3 text-center">
            <div className="flex items-center justify-center gap-1.5 text-xs font-medium text-rose-400 mb-1">
              <Frown className="h-3.5 w-3.5" />
              <span>Negative</span>
            </div>
            <p className="text-xl font-bold text-[#F5F2EA]">{negPct.toFixed(1)}%</p>
            <p className="text-[10px] text-[#74736E] mt-0.5">{negCount.toLocaleString()} reviews</p>
          </div>
        </div>
      </div>

      {/* Star Rating Distribution Card */}
      <div className="premium-panel p-6 border border-[#292A2B] bg-[#151617]">
        <div className="mb-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="flex h-7 w-7 items-center justify-center rounded-md border border-[#292A2B] bg-[#1C1D1F] text-[#D4AF5A]">
              <Star className="h-4 w-4" />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-[#F5F2EA]">Rating Distribution</h3>
              <p className="text-[11px] text-[#74736E]">Customer 1-5 star verification</p>
            </div>
          </div>
          <span className="text-xs font-mono text-[#F0D58A] font-semibold">
            {statistics.average_rating ? statistics.average_rating.toFixed(2) : '0.0'} avg
          </span>
        </div>

        {/* 5-star to 1-star rows */}
        <div className="space-y-2 mt-3">
          {[5, 4, 3, 2, 1].map((stars) => {
            const count = ratingDist[String(stars)] || 0;
            const pct = Math.round((count / totalRatings) * 100);

            return (
              <div key={stars} className="flex items-center gap-3 text-xs">
                <div className="flex items-center gap-1 w-12 text-[#AAA79F] font-medium shrink-0">
                  <span>{stars}</span>
                  <Star className="h-3 w-3 fill-[#D4AF5A] text-[#D4AF5A]" />
                </div>

                <div className="flex-1 h-2 rounded-full bg-[#1C1D1F] overflow-hidden border border-[#242526]">
                  <div
                    style={{ width: `${pct}%` }}
                    className="h-full rounded-full bg-[#D4AF5A] transition-all duration-500"
                  />
                </div>

                <span className="w-10 text-right text-[11px] text-[#AAA79F] font-mono shrink-0">
                  {pct}%
                </span>
                <span className="w-14 text-right text-[10px] text-[#74736E] font-mono shrink-0">
                  ({count.toLocaleString()})
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};
