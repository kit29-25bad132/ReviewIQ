import React from 'react';
import { Star, MessageSquare, ArrowLeft, RefreshCw, Tag, ShieldCheck } from 'lucide-react';
import { ProductSummary, ProductStatistics } from '../types/ecommerce';

interface ProductHeaderProps {
  product: ProductSummary;
  statistics: ProductStatistics;
  onBack: () => void;
  onRefresh?: () => void;
  isRefreshing?: boolean;
}

export const ProductHeader: React.FC<ProductHeaderProps> = ({
  product,
  statistics,
  onBack,
  onRefresh,
  isRefreshing = false,
}) => {
  const rating = statistics.average_rating || product.average_rating || 0;
  const reviewCount = statistics.review_count || product.review_count || 0;

  return (
    <div className="border-b border-[#292A2B] bg-[#121314]/80 py-6 sm:py-8">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        {/* Navigation & Actions */}
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <button
            onClick={onBack}
            className="flex items-center gap-2 rounded-lg border border-[#292A2B] bg-[#161719] px-3 py-1.5 text-xs text-[#AAA79F] transition hover:border-[#D4AF5A]/40 hover:text-[#F5F2EA]"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            Back to Search
          </button>

          <div className="flex items-center gap-2">
            <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-500/30 bg-emerald-950/20 px-3 py-1 text-[11px] text-emerald-400">
              <ShieldCheck className="h-3.5 w-3.5" />
              Verified Dataset Intelligence
            </span>

            {onRefresh && (
              <button
                onClick={onRefresh}
                disabled={isRefreshing}
                className="flex items-center gap-1.5 rounded-lg border border-[#292A2B] bg-[#161719] px-3 py-1.5 text-xs text-[#AAA79F] transition hover:text-[#F5F2EA] disabled:opacity-50"
                title="Refresh Intelligence Data"
              >
                <RefreshCw className={`h-3 w-3 ${isRefreshing ? 'animate-spin text-[#D4AF5A]' : ''}`} />
                <span className="hidden sm:inline">Recompute</span>
              </button>
            )}
          </div>
        </div>

        {/* Product Identity */}
        <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
          <div className="flex-1 min-w-0">
            <div className="flex flex-wrap items-center gap-2 mb-2">
              {product.category && (
                <span className="inline-flex items-center gap-1 rounded bg-[#1C1D1F] px-2.5 py-0.5 text-xs font-medium text-[#AAA79F] border border-[#2A2B2D]">
                  <Tag className="h-3 w-3 text-[#D4AF5A]" />
                  {product.category}
                </span>
              )}
              <span className="text-xs font-mono text-[#74736E]">
                ASIN: {product.product_id}
              </span>
            </div>

            <h1 className="text-2xl sm:text-3xl font-semibold tracking-tight text-[#F5F2EA] leading-tight">
              {product.product_title}
            </h1>
          </div>

          {/* Quick Metrics Bar */}
          <div className="flex flex-wrap items-center gap-3 shrink-0">
            {/* Rating Box */}
            <div className="flex items-center gap-3 rounded-xl border border-[#292A2B] bg-[#17181A] px-4 py-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg border border-[#D4AF5A]/30 bg-[#211E17] text-[#F0D58A]">
                <Star className="h-5 w-5 fill-[#D4AF5A] text-[#D4AF5A]" />
              </div>
              <div>
                <div className="flex items-baseline gap-1">
                  <span className="text-2xl font-bold text-[#F5F2EA] tracking-tight">
                    {rating.toFixed(1)}
                  </span>
                  <span className="text-xs text-[#74736E]">/ 5.0</span>
                </div>
                <p className="text-[10px] uppercase tracking-wider text-[#AAA79F]">Overall Rating</p>
              </div>
            </div>

            {/* Review Count Box */}
            <div className="flex items-center gap-3 rounded-xl border border-[#292A2B] bg-[#17181A] px-4 py-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg border border-[#292A2B] bg-[#1E2022] text-[#AAA79F]">
                <MessageSquare className="h-5 w-5 text-[#D4AF5A]" />
              </div>
              <div>
                <p className="text-2xl font-bold text-[#F5F2EA] tracking-tight">
                  {reviewCount.toLocaleString()}
                </p>
                <p className="text-[10px] uppercase tracking-wider text-[#AAA79F]">Reviews Analyzed</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
