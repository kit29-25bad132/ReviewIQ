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
  FileText,
  RotateCcw,
} from 'lucide-react';
import { ReviewsPaginationResponse } from '../types/ecommerce';
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
      <div className="flex items-center gap-0.5">
        {[1, 2, 3, 4, 5].map((s) => (
          <Star
            key={s}
            className={`h-3.5 w-3.5 ${
              s <= clamped ? 'fill-amber-400 text-amber-400' : 'text-slate-200'
            }`}
          />
        ))}
      </div>
    );
  };

  const renderSentimentBadge = (sentiment: string) => {
    if (sentiment === 'positive') {
      return (
        <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2.5 py-0.5 text-[11px] font-semibold text-emerald-700">
          <ThumbsUp className="h-3 w-3" />
          <span>Positive</span>
        </span>
      );
    }
    if (sentiment === 'negative') {
      return (
        <span className="inline-flex items-center gap-1 rounded-full bg-rose-50 px-2.5 py-0.5 text-[11px] font-semibold text-rose-700">
          <ThumbsDown className="h-3 w-3" />
          <span>Negative</span>
        </span>
      );
    }
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-amber-50 px-2.5 py-0.5 text-[11px] font-semibold text-amber-700">
        <MinusCircle className="h-3 w-3" />
        <span>Neutral</span>
      </span>
    );
  };

  return (
    <div className="modern-card p-6 sm:p-8 space-y-6">
      {/* Header & Filters */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 border-b border-slate-100 pb-4">
        <div>
          <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
            <MessageSquare className="h-4 w-4 text-indigo-600" />
            Verified Customer Reviews
          </h2>
          <p className="text-xs text-slate-500">
            Real customer feedback for <strong className="text-slate-700 font-semibold">{productTitle}</strong>
          </p>
        </div>

        {/* Filter Controls */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Star Filter */}
          <div className="flex items-center gap-1">
            <span className="text-xs text-slate-400 mr-1 flex items-center gap-1">
              <Filter className="h-3 w-3 text-indigo-500" /> Rating:
            </span>
            {[5, 4, 3, 2, 1].map((star) => (
              <button
                key={star}
                onClick={() => setRatingFilter(ratingFilter === star ? undefined : star)}
                className={`rounded-lg border px-2.5 py-1 text-xs font-semibold transition ${
                  ratingFilter === star
                    ? 'border-indigo-600 bg-indigo-50 text-indigo-700'
                    : 'border-slate-200 bg-white text-slate-600 hover:border-slate-300'
                }`}
              >
                {star}★
              </button>
            ))}
          </div>

          {/* Sentiment Filter */}
          <div className="flex items-center gap-1 pl-2 border-l border-slate-200">
            {['positive', 'neutral', 'negative'].map((sent) => (
              <button
                key={sent}
                onClick={() => setSentimentFilter(sentimentFilter === sent ? undefined : sent)}
                className={`rounded-lg border px-2.5 py-1 text-xs capitalize font-medium transition ${
                  sentimentFilter === sent
                    ? 'border-indigo-600 bg-indigo-50 text-indigo-700 font-semibold'
                    : 'border-slate-200 bg-white text-slate-600 hover:border-slate-300'
                }`}
              >
                {sent}
              </button>
            ))}
          </div>

          {(ratingFilter !== undefined || sentimentFilter !== undefined) && (
            <button
              onClick={handleClearFilters}
              className="inline-flex items-center gap-1 rounded-lg border border-slate-200 bg-white px-2 py-1 text-xs text-slate-500 hover:text-slate-800 transition"
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
          <div className="inline-block h-6 w-6 animate-spin rounded-full border-2 border-indigo-600 border-t-transparent" />
          <p className="text-xs text-slate-500">Retrieving customer reviews...</p>
        </div>
      ) : error ? (
        <div className="rounded-xl border border-rose-200 bg-rose-50 p-5 text-center text-xs text-rose-700">
          {error}
        </div>
      ) : !data || data.items.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50/50 p-8 text-center space-y-2">
          <FileText className="h-6 w-6 text-slate-400 mx-auto" />
          <p className="text-sm font-semibold text-slate-800">No reviews match the selected filters.</p>
          <p className="text-xs text-slate-500">Try clearing your rating or sentiment filter.</p>
          <button
            onClick={handleClearFilters}
            className="primary-button mt-3 px-4 py-1.5 text-xs font-semibold"
          >
            Clear Filters
          </button>
        </div>
      ) : (
        <div className="space-y-4">
          <div className="flex items-center justify-between text-xs text-slate-400">
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
                className="rounded-xl border border-slate-200 bg-slate-50/40 p-5 space-y-3 transition hover:border-indigo-200 hover:bg-white"
              >
                <div className="flex items-center justify-between gap-3">
                  <div className="flex items-center gap-3">
                    <div className="flex h-8 w-8 items-center justify-center rounded-full bg-indigo-100 text-indigo-700 font-bold text-xs">
                      {review.product_title ? review.product_title.charAt(0).toUpperCase() : 'U'}
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        {renderStars(review.rating)}
                        <span className="text-xs font-bold text-slate-700">
                          {review.rating}.0 / 5.0
                        </span>
                      </div>
                      <span className="text-[10px] text-slate-400 font-mono">
                        Review ID: #{review.id}
                      </span>
                    </div>
                  </div>

                  {renderSentimentBadge(review.sentiment)}
                </div>

                <p className="text-xs sm:text-sm text-slate-700 leading-relaxed">
                  "{review.review_text}"
                </p>
              </article>
            ))}
          </div>

          {/* Pagination */}
          {data.total_pages > 1 && (
            <div className="flex items-center justify-between border-t border-slate-100 pt-4">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page <= 1}
                className="secondary-button inline-flex items-center gap-1 px-3 py-1.5 text-xs font-semibold disabled:opacity-40"
              >
                <ChevronLeft className="h-4 w-4" />
                <span>Previous</span>
              </button>

              <div className="flex items-center gap-1.5 text-xs text-slate-500 font-medium">
                Page <span className="font-bold text-slate-800">{page}</span> of {data.total_pages}
              </div>

              <button
                onClick={() => setPage((p) => Math.min(data.total_pages, p + 1))}
                disabled={page >= data.total_pages}
                className="secondary-button inline-flex items-center gap-1 px-3 py-1.5 text-xs font-semibold disabled:opacity-40"
              >
                <span>Next</span>
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
