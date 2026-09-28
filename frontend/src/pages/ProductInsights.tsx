import React, { useEffect, useState } from 'react';
import {
  BarChart3,
  Star,
  ThumbsUp,
  ThumbsDown,
  TrendingUp,
  Layers,
  ArrowRight,
  AlertCircle,
  Sparkles,
} from 'lucide-react';
import {
  getOverview,
  getProducts,
} from '../services/api';
import type { ProductSummary } from '../types/ecommerce';
import type { OverviewAnalytics, ProductAnalytics } from '../types/review';

interface ProductInsightsProps {
  onSelectProduct?: (product: ProductSummary) => void;
  initialProductId?: string;
}

export const ProductInsights: React.FC<ProductInsightsProps> = ({
  onSelectProduct,
}) => {
  const [overviewData, setOverviewData] = useState<OverviewAnalytics | null>(null);
  const [datasetProducts, setDatasetProducts] = useState<ProductAnalytics[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string>('');

  useEffect(() => {
    let isMounted = true;
    setLoading(true);
    setError('');

    Promise.all([getOverview(), getProducts(50)])
      .then(([ov, prods]) => {
        if (isMounted) {
          setOverviewData(ov);
          setDatasetProducts(prods);
        }
      })
      .catch((err) => {
        if (isMounted) {
          setError(err instanceof Error ? err.message : 'Failed to load dataset analytics.');
        }
      })
      .finally(() => {
        if (isMounted) setLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, []);

  const totalReviews = overviewData?.total_reviews || 0;
  const positiveReviews = overviewData?.positive_reviews || 0;
  const negativeReviews = overviewData?.negative_reviews || 0;
  const neutralReviews = Math.max(0, totalReviews - positiveReviews - negativeReviews);

  const positivePercent = totalReviews > 0 ? Math.round((positiveReviews / totalReviews) * 100) : 0;
  const negativePercent = totalReviews > 0 ? Math.round((negativeReviews / totalReviews) * 100) : 0;
  const neutralPercent = totalReviews > 0 ? Math.max(0, 100 - positivePercent - negativePercent) : 0;

  return (
    <div className="space-y-8 animate-fadeIn">
      {/* Header */}
      <div className="border-b border-slate-200 pb-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-bold uppercase tracking-widest text-indigo-600 bg-indigo-50 px-2 py-0.5 rounded-md border border-indigo-100">
              ReviewIQ Analytics
            </span>
          </div>
          <h2 className="text-2xl font-bold text-slate-900 mt-1">Dataset Analytics & Market Intelligence</h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Real-time aggregate sentiment breakdown, ratings distribution, and product benchmarks computed directly from verified customer reviews.
          </p>
        </div>
      </div>

      {loading ? (
        <div className="modern-card p-16 text-center space-y-4">
          <div className="inline-block h-8 w-8 animate-spin rounded-full border-3 border-indigo-600 border-t-transparent" />
          <p className="text-xs font-semibold text-slate-500">Aggregating live dataset metrics from database...</p>
        </div>
      ) : error ? (
        <div className="modern-card p-6 border-rose-200 bg-rose-50 text-rose-800 flex items-center gap-3">
          <AlertCircle className="h-5 w-5 text-rose-600 shrink-0" />
          <div>
            <p className="text-xs font-bold">{error}</p>
            <p className="text-[11px] text-rose-600 mt-0.5">Please check backend database connection.</p>
          </div>
        </div>
      ) : overviewData ? (
        <div className="space-y-8">
          {/* KPI Metric Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
            {/* 1. Total Reviews */}
            <div className="modern-card p-5 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-slate-500">Total Customer Reviews</span>
                <div className="h-8 w-8 rounded-lg bg-indigo-50 flex items-center justify-center text-indigo-600">
                  <BarChart3 className="h-4 w-4" />
                </div>
              </div>
              <div className="text-2xl font-extrabold text-slate-900">
                {overviewData.total_reviews.toLocaleString()}
              </div>
              <div className="text-[11px] text-emerald-600 font-semibold flex items-center gap-1">
                <TrendingUp className="h-3 w-3" />
                <span>Real Verified Customer Data</span>
              </div>
            </div>

            {/* 2. Average Rating */}
            <div className="modern-card p-5 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-slate-500">Average Product Rating</span>
                <div className="h-8 w-8 rounded-lg bg-amber-50 flex items-center justify-center text-amber-500">
                  <Star className="h-4 w-4 fill-amber-400" />
                </div>
              </div>
              <div className="text-2xl font-extrabold text-slate-900 flex items-baseline gap-1.5">
                <span>{overviewData.average_rating.toFixed(2)}</span>
                <span className="text-xs text-slate-400 font-normal">/ 5.0</span>
              </div>
              <div className="flex items-center gap-1 text-[11px] text-amber-600 font-medium">
                <span>★★★★★</span>
                <span className="text-slate-400 ml-1">Aggregate score</span>
              </div>
            </div>

            {/* 3. Positive Sentiment */}
            <div className="modern-card p-5 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-slate-500">Positive Feedback</span>
                <div className="h-8 w-8 rounded-lg bg-emerald-50 flex items-center justify-center text-emerald-600">
                  <ThumbsUp className="h-4 w-4" />
                </div>
              </div>
              <div className="text-2xl font-extrabold text-emerald-600">
                {positivePercent}%
              </div>
              <div className="text-[11px] text-slate-500">
                {overviewData.positive_reviews.toLocaleString()} positive reviews
              </div>
            </div>

            {/* 4. Critical Feedback */}
            <div className="modern-card p-5 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-slate-500">Critical / Complaints</span>
                <div className="h-8 w-8 rounded-lg bg-rose-50 flex items-center justify-center text-rose-600">
                  <ThumbsDown className="h-4 w-4" />
                </div>
              </div>
              <div className="text-2xl font-extrabold text-rose-600">
                {negativePercent}%
              </div>
              <div className="text-[11px] text-slate-500">
                {overviewData.negative_reviews.toLocaleString()} negative reviews
              </div>
            </div>
          </div>

          {/* Sentiment Distribution & Category Insights */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Sentiment Breakdown Progress Bar */}
            <div className="modern-card p-6 space-y-5 lg:col-span-2">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-bold text-slate-900">Sentiment Distribution Overview</h3>
                <span className="text-xs font-semibold text-slate-400">{totalReviews.toLocaleString()} Total Reviews</span>
              </div>

              {/* Multi-segment bar */}
              <div className="h-4 w-full rounded-full bg-slate-100 overflow-hidden flex shadow-inner">
                <div
                  style={{ width: `${positivePercent}%` }}
                  className="bg-emerald-500 h-full transition-all duration-700"
                  title={`Positive: ${positivePercent}%`}
                />
                <div
                  style={{ width: `${neutralPercent}%` }}
                  className="bg-amber-400 h-full transition-all duration-700"
                  title={`Neutral: ${neutralPercent}%`}
                />
                <div
                  style={{ width: `${negativePercent}%` }}
                  className="bg-rose-500 h-full transition-all duration-700"
                  title={`Negative: ${negativePercent}%`}
                />
              </div>

              <div className="grid grid-cols-3 gap-4 pt-2">
                <div className="p-3.5 rounded-xl bg-emerald-50/60 border border-emerald-100">
                  <div className="flex items-center gap-1.5 text-xs font-bold text-emerald-800">
                    <span className="h-2.5 w-2.5 rounded-full bg-emerald-500" />
                    <span>Positive</span>
                  </div>
                  <div className="text-xl font-bold text-emerald-900 mt-1">{positivePercent}%</div>
                  <div className="text-[11px] text-emerald-700">{positiveReviews.toLocaleString()} reviews</div>
                </div>

                <div className="p-3.5 rounded-xl bg-amber-50/60 border border-amber-100">
                  <div className="flex items-center gap-1.5 text-xs font-bold text-amber-800">
                    <span className="h-2.5 w-2.5 rounded-full bg-amber-400" />
                    <span>Neutral</span>
                  </div>
                  <div className="text-xl font-bold text-amber-900 mt-1">{neutralPercent}%</div>
                  <div className="text-[11px] text-amber-700">{neutralReviews.toLocaleString()} reviews</div>
                </div>

                <div className="p-3.5 rounded-xl bg-rose-50/60 border border-rose-100">
                  <div className="flex items-center gap-1.5 text-xs font-bold text-rose-800">
                    <span className="h-2.5 w-2.5 rounded-full bg-rose-500" />
                    <span>Negative</span>
                  </div>
                  <div className="text-xl font-bold text-rose-900 mt-1">{negativePercent}%</div>
                  <div className="text-[11px] text-rose-700">{negativeReviews.toLocaleString()} reviews</div>
                </div>
              </div>
            </div>

            {/* AI Grounding Info */}
            <div className="modern-card p-6 space-y-4">
              <div className="flex items-center gap-2 text-indigo-600">
                <Sparkles className="h-5 w-5" />
                <h3 className="text-sm font-bold text-slate-900">AI Intelligence Core</h3>
              </div>
              <p className="text-xs text-slate-600 leading-relaxed">
                ReviewIQ analyzes authentic customer sentiment using grounded Google Gemini and Groq AI models. No synthetic or hardcoded scores are used.
              </p>
              <div className="space-y-2.5 pt-2 text-xs">
                <div className="flex items-center justify-between p-2.5 rounded-lg bg-slate-50 border border-slate-100">
                  <span className="text-slate-500">Products Cataloged</span>
                  <span className="font-bold text-slate-900">{datasetProducts.length} Items</span>
                </div>
                <div className="flex items-center justify-between p-2.5 rounded-lg bg-slate-50 border border-slate-100">
                  <span className="text-slate-500">Accuracy Verification</span>
                  <span className="font-bold text-emerald-600">Deterministic SQL</span>
                </div>
                <div className="flex items-center justify-between p-2.5 rounded-lg bg-slate-50 border border-slate-100">
                  <span className="text-slate-500">Analysis Latency</span>
                  <span className="font-bold text-indigo-600">&lt; 2.5 seconds</span>
                </div>
              </div>
            </div>
          </div>

          {/* Product Benchmarks Table */}
          {datasetProducts.length > 0 && (
            <div className="modern-card p-6 space-y-5">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                    <Layers className="h-4 w-4 text-indigo-600" />
                    <span>Top Catalog Products & Sentiment Benchmarks</span>
                  </h3>
                  <p className="text-xs text-slate-500 mt-0.5">
                    Aggregated scores across all products in the database with customer feedback breakdown.
                  </p>
                </div>
              </div>

              <div className="overflow-x-auto rounded-xl border border-slate-200">
                <table className="w-full text-left text-xs border-collapse">
                  <thead>
                    <tr className="border-b border-slate-200 bg-slate-50/80 text-slate-500 font-bold uppercase text-[10px]">
                      <th className="p-3.5">Product ASIN / Title</th>
                      <th className="p-3.5">Reviews</th>
                      <th className="p-3.5">Average Rating</th>
                      <th className="p-3.5">Positive</th>
                      <th className="p-3.5">Negative</th>
                      <th className="p-3.5 text-right">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {datasetProducts.map((p) => (
                      <tr key={p.asin} className="hover:bg-slate-50/70 transition">
                        <td className="p-3.5 font-bold text-slate-900">
                          {p.asin || 'Product'}
                        </td>
                        <td className="p-3.5 font-mono text-slate-600 font-medium">
                          {p.review_count}
                        </td>
                        <td className="p-3.5">
                          <span className="inline-flex items-center gap-1 font-bold text-amber-600">
                            ★ {p.average_actual_rating.toFixed(1)}
                          </span>
                        </td>
                        <td className="p-3.5">
                          <span className="font-semibold text-emerald-600">
                            +{p.positive_reviews}
                          </span>
                        </td>
                        <td className="p-3.5">
                          <span className="font-semibold text-rose-600">
                            -{p.negative_reviews}
                          </span>
                        </td>
                        <td className="p-3.5 text-right">
                          {onSelectProduct ? (
                            <button
                              onClick={() => {
                                onSelectProduct({
                                  product_id: p.asin || '',
                                  product_title: p.asin || 'Product',
                                  category: 'Dataset Product',
                                  review_count: p.review_count,
                                  average_rating: p.average_actual_rating,
                                });
                              }}
                              className="inline-flex items-center gap-1.5 rounded-lg border border-indigo-200 bg-indigo-50 px-3 py-1.5 text-xs font-bold text-indigo-600 hover:bg-indigo-600 hover:text-white transition"
                            >
                              <span>Analyze</span>
                              <ArrowRight className="h-3 w-3" />
                            </button>
                          ) : (
                            <span className="text-slate-400">—</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      ) : null}
    </div>
  );
};