import React, { useState } from 'react';
import { History, Star, MessageSquare, Trash2, ArrowRight, Clock } from 'lucide-react';
import { getProductHistory, clearProductHistory, RecentProductHistoryItem } from '../services/historyStorage';
import { ProductSummary } from '../types/ecommerce';

interface HistoryPageProps {
  onSelectProduct: (product: ProductSummary) => void;
}

export const HistoryPage: React.FC<HistoryPageProps> = ({ onSelectProduct }) => {
  const [history, setHistory] = useState<RecentProductHistoryItem[]>(getProductHistory());

  const handleClear = () => {
    if (window.confirm('Are you sure you want to clear your local analysis history?')) {
      clearProductHistory();
      setHistory([]);
    }
  };

  const formatDate = (isoString: string) => {
    try {
      const d = new Date(isoString);
      return d.toLocaleDateString(undefined, {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch {
      return isoString;
    }
  };

  return (
    <div className="mx-auto max-w-7xl px-4 py-10 sm:px-6 lg:px-8 space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-[#292A2B] pb-6">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <div className="flex h-7 w-7 items-center justify-center rounded-lg border border-[#D4AF5A]/40 bg-[#1E1B15] text-[#D4AF5A]">
              <History className="h-4 w-4" />
            </div>
            <span className="text-xs font-semibold uppercase tracking-[0.2em] text-[#D4AF5A]">
              Analysis Log
            </span>
          </div>

          <h1 className="text-2xl sm:text-3xl font-semibold tracking-tight text-[#F5F2EA]">
            Recently Analyzed Products
          </h1>
          <p className="mt-1 text-sm text-[#AAA79F]">
            Quickly return to previously examined product intelligence dashboards
          </p>
        </div>

        {history.length > 0 && (
          <button
            onClick={handleClear}
            className="inline-flex items-center gap-2 rounded-lg border border-[#292A2B] bg-[#161719] px-3.5 py-2 text-xs font-medium text-rose-400 transition hover:border-rose-900/50 hover:bg-rose-950/20"
          >
            <Trash2 className="h-3.5 w-3.5" />
            Clear History
          </button>
        )}
      </div>

      {/* History Grid */}
      {history.length === 0 ? (
        <div className="premium-panel mx-auto max-w-md p-10 text-center border border-[#292A2B] my-8">
          <Clock className="mx-auto h-8 w-8 text-[#74736E] mb-3" />
          <h3 className="text-base font-semibold text-[#F5F2EA]">No Recent Products</h3>
          <p className="mt-2 text-xs leading-relaxed text-[#AAA79F]">
            Products you analyze will appear here for fast re-access during your work session.
          </p>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {history.map((item) => (
            <div
              key={item.productId}
              onClick={() =>
                onSelectProduct({
                  product_id: item.productId,
                  product_title: item.productTitle,
                  category: item.category,
                  review_count: item.reviewCount,
                  average_rating: item.overallRating,
                })
              }
              className="premium-panel premium-panel-hover p-5 cursor-pointer border border-[#292A2B] bg-[#151617] group flex flex-col justify-between"
              role="button"
              tabIndex={0}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  onSelectProduct({
                    product_id: item.productId,
                    product_title: item.productTitle,
                    category: item.category,
                    review_count: item.reviewCount,
                    average_rating: item.overallRating,
                  });
                }
              }}
            >
              <div>
                <div className="flex items-center justify-between gap-2 mb-2">
                  <span className="rounded bg-[#1C1D1F] px-2 py-0.5 text-[10px] font-mono text-[#74736E] border border-[#2A2B2D]">
                    {item.productId}
                  </span>
                  <span className="text-[10px] text-[#74736E]">
                    {formatDate(item.analyzedAt)}
                  </span>
                </div>

                <h4 className="line-clamp-2 text-sm font-semibold text-[#F5F2EA] group-hover:text-[#F0D58A] transition-colors">
                  {item.productTitle}
                </h4>
              </div>

              <div className="mt-5 pt-3 border-t border-[#242526] flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="flex items-center gap-1 text-xs font-semibold text-[#F0D58A]">
                    <Star className="h-3.5 w-3.5 fill-[#D4AF5A] text-[#D4AF5A]" />
                    <span>{item.overallRating ? item.overallRating.toFixed(1) : 'N/A'}</span>
                  </div>

                  <div className="flex items-center gap-1 text-[11px] text-[#AAA79F]">
                    <MessageSquare className="h-3 w-3 text-[#74736E]" />
                    <span>{item.reviewCount.toLocaleString()}</span>
                  </div>
                </div>

                <span className="flex items-center gap-1 text-xs font-medium text-[#D4AF5A] group-hover:translate-x-1 transition-transform">
                  View Intelligence
                  <ArrowRight className="h-3.5 w-3.5" />
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
