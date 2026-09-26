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
      <div className="flex items-center gap-0.5 text-[#D4AF5A]">
        {[1, 2, 3, 4, 5].map((s) => (
          <Star
            key={s}
            className={`h-3 w-3 ${
              s <= clamped ? 'fill-[#D4AF5A] text-[#D4AF5A]' : 'text-[#292A2B]'
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
          <span className="inline-flex items-center gap-1 rounded border border-emerald-800/40 bg-emerald-950/40 px-2 py-0.5 text-[10px] font-semibold text-emerald-400">
            <ThumbsUp className="h-2.5 w-2.5" /> Positive
          </span>
        );
      case 'negative':
        return (
          <span className="inline-flex items-center gap-1 rounded border border-rose-800/40 bg-rose-950/40 px-2 py-0.5 text-[10px] font-semibold text-rose-400">
            <ThumbsDown className="h-2.5 w-2.5" /> Negative
          </span>
        );
      case 'neutral':
      default:
        return (
          <span className="inline-flex items-center gap-1 rounded border border-[#D4AF5A]/30 bg-[#1B1915] px-2 py-0.5 text-[10px] font-semibold text-[#D4AF5A]">
            <MinusCircle className="h-2.5 w-2.5" /> Neutral
          </span>
        );
    }
  };

  return (
    <div className="premium-panel p-6 space-y-6">
      {/* Section Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-[#292A2B] pb-4">
        <div>
          <h3 className="text-base font-medium text-[#F5F2EA] flex items-center gap-2">
            <MessageSquare className="h-4 w-4 text-[#D4AF5A]" />
            Customer Review Explorer
          </h3>
          <p className="text-xs text-[#74736E] mt-0.5">
            Browsing actual customer reviews from dataset for <strong className="text-[#AAA79F]">{productTitle}</strong>
          </p>
        </div>

        {/* Filter Controls */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Star Filter */}
          <div className="flex items-center gap-1">
            <span className="text-xs text-[#74736E] mr-1 flex items-center gap-1">
              <Filter className="h-3 w-3 text-[#D4AF5A]" /> Rating:
            </span>
            {[5, 4, 3, 2, 1].map((star) => (
              <button
                key={star}
                onClick={() => setRatingFilter(ratingFilter === star ? undefined : star)}
                className={`rounded-lg border px-2 py-1 text-xs font-semibold transition ${
                  ratingFilter === star
                    ? 'border-[#D4AF5A] bg-[#1B1915] text-[#F0D58A]'
                    : 'border-[#292A2B] bg-[#151617] text-[#AAA79F] hover:border-[#D4AF5A]/30 hover:text-[#F5F2EA]'
                }`}
              >
                {star}★
              </button>
            ))}
          </div>

          {/* Sentiment Filter */}
          <div className="flex items-center gap-1 pl-2 border-l border-[#292A2B]">
            {['positive', 'neutral', 'negative'].map((sent) => (
              <button
                key={sent}
                onClick={() => setSentimentFilter(sentimentFilter === sent ? undefined : sent)}
                className={`rounded-lg border px-2.5 py-1 text-xs capitalize transition ${
                  sentimentFilter === sent
                    ? 'border-[#D4AF5A] bg-[#1B1915] text-[#F0D58A]'
                    : 'border-[#292A2B] bg-[#151617] text-[#AAA79F] hover:border-[#D4AF5A]/30 hover:text-[#F5F2EA]'
                }`}
              >
                {sent}
              </button>
            ))}
          </div>

          {(ratingFilter !== undefined || sentimentFilter !== undefined) && (
            <button
              onClick={handleClearFilters}
              className="inline-flex items-center gap-1 rounded-lg border border-[#292A2B] bg-[#151617] px-2 py-1 text-xs text-[#AAA79F] hover:text-[#F5F2EA] transition"
              title="Clear all filters"
            >
              <RotateCcw className="h-3 w-3" />
              <span>Reset</span>
            </button>
          )}
        </div>
      </div>

      {/* Reviews List */}
      {loading ? (
        <div className="py-12 text-center space-y-2">
          <div className="inline-block h-6 w-6 animate-spin rounded-full border-2 border-[#D4AF5A] border-t-transparent" />
          <p className="text-xs text-[#AAA79F]">Retrieving paginated customer reviews...</p>
        </div>
      ) : error ? (
        <div className="rounded-xl border border-rose-900/40 bg-rose-950/20 p-5 text-center text-xs text-rose-300">
          {error}
        </div>
      ) : !data || data.items.length === 0 ? (
        <div className="rounded-xl border border-dashed border-[#292A2B] bg-[#151617]/50 p-8 text-center space-y-2">
          <FileText className="h-6 w-6 text-[#74736E] mx-auto" />
          <p className="text-sm font-medium text-[#F5F2EA]">No reviews match the selected filters.</p>
          <p className="text-xs text-[#74736E]">Try clearing your rating or sentiment filter.</p>
          <button
            onClick={handleClearFilters}
            className="gold-button mt-3 px-4 py-1.5 text-xs font-semibold"
          >
            Clear Filters
          </button>
        </div>
      ) : (
        <div className="space-y-4">
          <div className="flex items-center justify-between text-xs text-[#74736E]">
            <span>
              Showing {((page - 1) * PAGE_SIZE) + 1} - {Math.min(page * PAGE_SIZE, data.total)} of{' '}
              {data.total.toLocaleString()} reviews
            </span>
            <span>Page {data.page} of {data.total_pages}</span>
          </div>

          <div className="space-y-3">
            {data.items.map((review) => (
              <article
                key={review.id}
                className="rounded-xl border border-[#292A2B] bg-[#151617] p-5 space-y-3 transition hover:border-[#D4AF5A]/30"
              >
                <div className="flex items-center justify-between gap-3">
                  <div className="flex items-center gap-2.5">
                    {renderStars(review.rating)}
                    <span className="text-xs font-medium text-[#D4AF5A]">
                      {review.rating}.0 / 5.0
                    </span>
                  </div>

                  <div className="flex items-center gap-2">
                    {renderSentiment(review.sentiment)}
                    <span className="text-[10px] text-[#74736E] font-mono">
                      #{review.id}
                    </span>
                  </div>
                </div>

                <p className="text-xs sm:text-sm leading-relaxed text-[#F5F2EA]">
                  "{review.review_text}"
                </p>

                <div className="flex items-center justify-between pt-2 border-t border-[#292A2B]/60 text-[11px] text-[#74736E]">
                  <span>Product: {review.product_title}</span>
                  <button
                    onClick={() => setSelectedReviewModal(review)}
                    className="text-[#D4AF5A] hover:underline"
                  >
                    View Full
                  </button>
                </div>
              </article>
            ))}
          </div>

          {/* Pagination Controls */}
          {data.total_pages > 1 && (
            <div className="flex items-center justify-between pt-4 border-t border-[#292A2B]">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page <= 1}
                className="inline-flex items-center gap-1.5 rounded-lg border border-[#292A2B] bg-[#151617] px-3 py-1.5 text-xs text-[#AAA79F] hover:border-[#D4AF5A]/30 hover:text-[#F5F2EA] disabled:opacity-40 transition"
              >
                <ChevronLeft className="h-4 w-4" />
                <span>Previous</span>
              </button>

              <div className="flex items-center gap-1">
                {Array.from({ length: Math.min(5, data.total_pages) }, (_, idx) => {
                  let pageNum: number;
                  if (data.total_pages <= 5) {
                    pageNum = idx + 1;
                  } else if (page <= 3) {
                    pageNum = idx + 1;
                  } else if (page >= data.total_pages - 2) {
                    pageNum = data.total_pages - 4 + idx;
                  } else {
                    pageNum = page - 2 + idx;
                  }

                  return (
                    <button
                      key={pageNum}
                      onClick={() => setPage(pageNum)}
                      className={`h-7 w-7 rounded-lg text-xs font-semibold transition ${
                        page === pageNum
                          ? 'border border-[#D4AF5A] bg-[#1B1915] text-[#F0D58A]'
                          : 'border border-[#292A2B] bg-[#151617] text-[#AAA79F] hover:border-[#D4AF5A]/30 hover:text-[#F5F2EA]'
                      }`}
                    >
                      {pageNum}
                    </button>
                  );
                })}
              </div>

              <button
                onClick={() => setPage((p) => Math.min(data.total_pages, p + 1))}
                disabled={page >= data.total_pages}
                className="inline-flex items-center gap-1.5 rounded-lg border border-[#292A2B] bg-[#151617] px-3 py-1.5 text-xs text-[#AAA79F] hover:border-[#D4AF5A]/30 hover:text-[#F5F2EA] disabled:opacity-40 transition"
              >
                <span>Next</span>
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>
          )}
        </div>
      )}

      {/* Full Review Modal */}
      {selectedReviewModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
          <div className="relative max-h-[85vh] w-full max-w-lg overflow-hidden rounded-2xl border border-[#292A2B] bg-[#111213] shadow-2xl p-6 space-y-4">
            <div className="flex items-center justify-between border-b border-[#292A2B] pb-3">
              <div className="flex items-center gap-2">
                {renderStars(selectedReviewModal.rating)}
                <span className="text-xs text-[#D4AF5A] font-semibold">
                  {selectedReviewModal.rating}.0 / 5.0
                </span>
              </div>
              <button
                onClick={() => setSelectedReviewModal(null)}
                className="rounded-lg p-1.5 text-[#74736E] hover:bg-[#1C1D1F] hover:text-[#F5F2EA] transition"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="space-y-3">
              <div className="flex items-center justify-between text-xs text-[#74736E]">
                <span>Product: {selectedReviewModal.product_title}</span>
                {renderSentiment(selectedReviewModal.sentiment)}
              </div>
              <p className="text-sm leading-relaxed text-[#F5F2EA] bg-[#151617] p-4 rounded-xl border border-[#292A2B]">
                "{selectedReviewModal.review_text}"
              </p>
            </div>

            <div className="pt-3 border-t border-[#292A2B] text-right">
              <button
                onClick={() => setSelectedReviewModal(null)}
                className="rounded-lg border border-[#292A2B] bg-[#151617] px-4 py-1.5 text-xs text-[#F5F2EA] hover:bg-[#1C1D1F] transition"
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
