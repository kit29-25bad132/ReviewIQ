import React, { useEffect, useState } from 'react';
import {
  MessageSquare,
  Star,
  ThumbsUp,
  ThumbsDown,
  MinusCircle,
  Filter,
  ChevronLeft,
  ChevronRight,
  Database,
  X,
  FileText,
  RotateCcw,
} from 'lucide-react';
import { ReviewItem, ReviewsPaginationResponse } from '../types/ecommerce';
import { getProductReviews } from '../services/api';

interface ReviewListProps {
  productId: string;
  productTitle: string;
}

const PAGE_SIZE = 10;

export const ReviewList: React.FC<ReviewListProps> = ({ productId, productTitle }) => {
  const [data, setData] = useState<ReviewsPaginationResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string>('');
  const [page, setPage] = useState<number>(1);
  const [ratingFilter, setRatingFilter] = useState<number | undefined>();
  const [sentimentFilter, setSentimentFilter] = useState<string | undefined>();
  const [selectedReviewModal, setSelectedReviewModal] = useState<ReviewItem | null>(null);

  const fetchReviews = () => {
    setLoading(true);
    setError('');
    getProductReviews(productId, {
      page,
      limit: PAGE_SIZE,
      rating: ratingFilter,
      sentiment: sentimentFilter,
    })
      .then((res) => {
        setData(res);
      })
      .catch((err) => {
        setError(err.response?.data?.detail || 'Failed to fetch reviews.');
      })
      .finally(() => {
        setLoading(false);
      });
  };

  useEffect(() => {
    setPage(1);
  }, [productId, ratingFilter, sentimentFilter]);

  useEffect(() => {
    fetchReviews();
  }, [productId, page, ratingFilter, sentimentFilter]);

  const handleClearFilters = () => {
    setRatingFilter(undefined);
    setSentimentFilter(undefined);
    setPage(1);
  };

  const renderStars = (rating: number) => {
    const clamped = Math.max(1, Math.min(5, Math.round(rating)));
    return (
      <div className="flex items-center gap-0.5 text-amber-400">
        {[1, 2, 3, 4, 5].map((s) => (
          <Star
            key={s}
            className={`h-3.5 w-3.5 ${
              s <= clamped ? 'fill-amber-400 text-amber-400' : 'text-slate-600'
            }`}
          />
        ))}
      </div>
    );
  };

  const renderSentiment = (sentiment: string) => {
    const s = (sentiment || '').toLowerCase();
    switch (s) {
      case 'positive':
        return (
          <span className="inline-flex items-center gap-1 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 text-[10px] font-semibold text-emerald-400">
            <ThumbsUp className="h-2.5 w-2.5" /> Positive
          </span>
        );
      case 'negative':
        return (
          <span className="inline-flex items-center gap-1 rounded-full border border-rose-500/30 bg-rose-500/10 px-2 py-0.5 text-[10px] font-semibold text-rose-400">
            <ThumbsDown className="h-2.5 w-2.5" /> Negative
          </span>
        );
      case 'neutral':
      default:
        return (
          <span className="inline-flex items-center gap-1 rounded-full border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 text-[10px] font-semibold text-amber-400">
            <MinusCircle className="h-2.5 w-2.5" /> Neutral
          </span>
        );
    }
  };

  const isFilterActive = ratingFilter !== undefined || sentimentFilter !== undefined;

  return (
    <div className="relative overflow-hidden rounded-2xl border border-white/10 bg-[#111827]/80 p-6 backdrop-blur-xl shadow-glass space-y-5">
      {/* Header and Filter Controls */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800 pb-4">
        <div>
          <h3 className="text-base font-bold text-white flex items-center gap-2">
            <MessageSquare className="h-4 w-4 text-purple-400" />
            Customer Reviews from Dataset
          </h3>
          <p className="text-[11px] font-mono text-slate-400 mt-0.5">
            Showing actual unmodified review text for <strong className="text-slate-200">{productTitle}</strong>
          </p>
        </div>

        {/* Filter Toolbar */}
        <div className="flex flex-wrap items-center gap-2 text-xs">
          {/* Rating filter */}
          <div className="flex items-center gap-1.5 rounded-xl border border-slate-700 bg-[#0B0F17] px-2.5 py-1.5">
            <Filter className="h-3 w-3 text-slate-400" />
            <select
              value={ratingFilter ?? ''}
              onChange={(e) => setRatingFilter(e.target.value ? Number(e.target.value) : undefined)}
              className="bg-transparent text-slate-300 focus:outline-none cursor-pointer text-xs"
            >
              <option value="" className="bg-[#111827]">
                All Star Ratings
              </option>
              <option value="5" className="bg-[#111827]">
                5 Stars
              </option>
              <option value="4" className="bg-[#111827]">
                4 Stars
              </option>
              <option value="3" className="bg-[#111827]">
                3 Stars
              </option>
              <option value="2" className="bg-[#111827]">
                2 Stars
              </option>
              <option value="1" className="bg-[#111827]">
                1 Star
              </option>
            </select>
          </div>

          {/* Sentiment filter */}
          <div className="flex items-center gap-1.5 rounded-xl border border-slate-700 bg-[#0B0F17] px-2.5 py-1.5">
            <select
              value={sentimentFilter ?? ''}
              onChange={(e) => setSentimentFilter(e.target.value || undefined)}
              className="bg-transparent text-slate-300 focus:outline-none cursor-pointer text-xs"
            >
              <option value="" className="bg-[#111827]">
                All Sentiments
              </option>
              <option value="positive" className="bg-[#111827]">
                Positive
              </option>
              <option value="neutral" className="bg-[#111827]">
                Neutral
              </option>
              <option value="negative" className="bg-[#111827]">
                Negative
              </option>
            </select>
          </div>

          {/* Clear filter button */}
          {isFilterActive && (
            <button
              onClick={handleClearFilters}
              className="inline-flex items-center gap-1 rounded-xl border border-slate-700 bg-slate-800/80 px-2.5 py-1.5 text-slate-300 hover:text-white transition"
              title="Reset all filters"
            >
              <RotateCcw className="h-3 w-3" />
              <span>Reset</span>
            </button>
          )}
        </div>
      </div>

      {/* Review List */}
      {loading ? (
        <div className="py-12 text-center space-y-2">
          <div className="inline-block h-6 w-6 animate-spin rounded-full border-2 border-purple-400 border-t-transparent" />
          <p className="text-xs text-slate-400 font-mono">Loading reviews from dataset...</p>
        </div>
      ) : error ? (
        <div className="rounded-xl border border-rose-500/30 bg-rose-500/10 p-5 text-center text-xs text-rose-300">
          {error}
        </div>
      ) : !data || data.items.length === 0 ? (
        <div className="rounded-xl border border-dashed border-slate-800 p-8 text-center space-y-2">
          <FileText className="h-6 w-6 text-slate-500 mx-auto" />
          <p className="text-xs text-slate-300 font-medium">No reviews match the selected filter criteria.</p>
          {isFilterActive && (
            <button
              onClick={handleClearFilters}
              className="text-xs text-purple-400 hover:underline inline-block mt-1"
            >
              Clear filters to view all reviews
            </button>
          )}
        </div>
      ) : (
        <div className="space-y-4">
          <div className="flex items-center justify-between text-xs text-slate-400 font-mono px-1">
            <span>
              Showing {data.items.length} of {data.total.toLocaleString()} reviews
            </span>
            <span className="flex items-center gap-1 text-[11px] text-cyan-400">
              <Database className="h-3 w-3" />
              <span>Source: ReviewIQ Product Review Dataset</span>
            </span>
          </div>

          <div className="grid grid-cols-1 gap-3.5">
            {data.items.map((r) => {
              const isLong = r.review_text.length > 280;
              return (
                <div
                  key={r.id}
                  className="rounded-xl border border-slate-800 bg-[#0B0F17]/85 p-4 space-y-2.5 hover:border-purple-500/30 transition"
                >
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex items-center gap-2.5">
                      {renderStars(r.rating)}
                      <span className="font-mono text-xs font-bold text-white">
                        {r.rating}/5
                      </span>
                      {renderSentiment(r.sentiment)}
                    </div>

                    <span className="text-[11px] font-mono text-slate-500">
                      ID: #{r.id}
                    </span>
                  </div>

                  {/* Review Text */}
                  <div className="text-xs sm:text-sm text-slate-200 leading-relaxed">
                    "{r.review_text}"
                  </div>

                  {isLong && (
                    <button
                      onClick={() => setSelectedReviewModal(r)}
                      className="text-xs text-purple-400 hover:text-purple-300 font-medium inline-flex items-center gap-1 pt-1"
                    >
                      Read full review
                    </button>
                  )}
                </div>
              );
            })}
          </div>

          {/* Pagination */}
          <div className="flex items-center justify-between border-t border-slate-800 pt-4 text-xs">
            <button
              disabled={page <= 1}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              className="inline-flex items-center gap-1 rounded-xl border border-slate-700 bg-[#0B0F17] px-3 py-1.5 font-semibold text-slate-300 hover:bg-slate-800 disabled:opacity-40 disabled:cursor-not-allowed transition"
            >
              <ChevronLeft className="h-3.5 w-3.5" />
              Previous
            </button>

            <span className="font-mono text-slate-400">
              Page <span className="text-white font-bold">{page}</span> of{' '}
              <span className="text-white font-bold">{data.total_pages}</span>
            </span>

            <button
              disabled={page >= data.total_pages}
              onClick={() => setPage((p) => Math.min(data.total_pages, p + 1))}
              className="inline-flex items-center gap-1 rounded-xl border border-slate-700 bg-[#0B0F17] px-3 py-1.5 font-semibold text-slate-300 hover:bg-slate-800 disabled:opacity-40 disabled:cursor-not-allowed transition"
            >
              Next
              <ChevronRight className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
      )}

      {/* Full Review Modal */}
      {selectedReviewModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4 backdrop-blur-sm animate-fadeIn">
          <div className="relative w-full max-w-xl max-h-[85vh] overflow-y-auto rounded-2xl border border-purple-500/30 bg-[#0B0F17] p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2">
                {renderStars(selectedReviewModal.rating)}
                <span className="font-mono font-bold text-white text-xs">
                  {selectedReviewModal.rating}/5
                </span>
                {renderSentiment(selectedReviewModal.sentiment)}
              </div>
              <button
                onClick={() => setSelectedReviewModal(null)}
                className="rounded-lg p-1 text-slate-400 hover:bg-slate-800 hover:text-white transition"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="text-xs font-mono text-cyan-300">
              Product: {selectedReviewModal.product_title}
            </div>

            <div className="rounded-xl border border-slate-800 bg-[#111827]/70 p-4 text-sm text-slate-200 leading-relaxed whitespace-pre-wrap">
              "{selectedReviewModal.review_text}"
            </div>

            <div className="flex justify-between items-center pt-2">
              <span className="text-[11px] font-mono text-slate-500">
                Source: ReviewIQ Product Review Dataset
              </span>
              <button
                onClick={() => setSelectedReviewModal(null)}
                className="rounded-xl bg-slate-800 px-4 py-2 text-xs font-semibold text-slate-200 hover:bg-slate-700"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
