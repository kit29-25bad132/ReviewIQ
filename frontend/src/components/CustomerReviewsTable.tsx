import React, { useEffect, useState } from 'react';
import { MessageSquare, Star, ChevronLeft, ChevronRight, Filter, Loader2 } from 'lucide-react';
import { ReviewItem, ReviewsPaginationResponse } from '../types/ecommerce';
import { getProductReviews } from '../services/api';

interface CustomerReviewsTableProps {
  productId: string;
  initialReviews?: ReviewItem[];
}

export const CustomerReviewsTable: React.FC<CustomerReviewsTableProps> = ({
  productId,
  initialReviews = [],
}) => {
  const [reviewsData, setReviewsData] = useState<ReviewsPaginationResponse | null>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [ratingFilter, setRatingFilter] = useState<number | undefined>(undefined);
  const [sentimentFilter, setSentimentFilter] = useState<string | undefined>(undefined);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedReviews, setExpandedReviews] = useState<Record<number, boolean>>({});

  const fetchReviews = async (page: number, rating?: number, sentiment?: string) => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await getProductReviews(productId, {
        page,
        limit: 10,
        rating: rating || undefined,
        sentiment: sentiment || undefined,
      });
      setReviewsData(response);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to retrieve reviews.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchReviews(currentPage, ratingFilter, sentimentFilter);
  }, [productId, currentPage, ratingFilter, sentimentFilter]);

  const handleRatingChange = (newRatingStr: string) => {
    setCurrentPage(1);
    setRatingFilter(newRatingStr ? Number(newRatingStr) : undefined);
  };

  const handleSentimentChange = (newSentimentStr: string) => {
    setCurrentPage(1);
    setSentimentFilter(newSentimentStr ? newSentimentStr : undefined);
  };

  const toggleExpand = (id: number) => {
    setExpandedReviews((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const items = reviewsData?.items || (currentPage === 1 ? initialReviews : []);
  const total = reviewsData?.total ?? initialReviews.length;
  const totalPages = reviewsData?.total_pages ?? Math.ceil(total / 10) ?? 1;

  return (
    <div className="premium-panel p-6 sm:p-7 border border-[#292A2B] bg-[#141517]">
      {/* Header and Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6 pb-5 border-b border-[#242526]">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <div className="flex h-7 w-7 items-center justify-center rounded-lg border border-[#D4AF5A]/40 bg-[#1E1B15] text-[#D4AF5A]">
              <MessageSquare className="h-4 w-4" />
            </div>
            <h3 className="text-sm font-semibold tracking-wide text-[#F5F2EA] uppercase">
              Customer Reviews Explorer
            </h3>
          </div>
          <p className="text-xs text-[#AAA79F]">
            Browse and filter through actual customer reviews from the dataset
          </p>
        </div>

        {/* Filter dropdowns */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Rating Filter */}
          <div className="flex items-center gap-1.5 rounded-lg border border-[#292A2B] bg-[#18191B] px-3 py-1.5 text-xs text-[#AAA79F]">
            <Star className="h-3.5 w-3.5 text-[#D4AF5A]" />
            <select
              value={ratingFilter ?? ''}
              onChange={(e) => handleRatingChange(e.target.value)}
              className="bg-transparent text-xs text-[#F5F2EA] focus:outline-none cursor-pointer"
            >
              <option value="" className="bg-[#18191B] text-[#F5F2EA]">All Ratings</option>
              <option value="5" className="bg-[#18191B] text-[#F5F2EA]">5 Stars</option>
              <option value="4" className="bg-[#18191B] text-[#F5F2EA]">4 Stars</option>
              <option value="3" className="bg-[#18191B] text-[#F5F2EA]">3 Stars</option>
              <option value="2" className="bg-[#18191B] text-[#F5F2EA]">2 Stars</option>
              <option value="1" className="bg-[#18191B] text-[#F5F2EA]">1 Star</option>
            </select>
          </div>

          {/* Sentiment Filter */}
          <div className="flex items-center gap-1.5 rounded-lg border border-[#292A2B] bg-[#18191B] px-3 py-1.5 text-xs text-[#AAA79F]">
            <Filter className="h-3.5 w-3.5 text-[#D4AF5A]" />
            <select
              value={sentimentFilter ?? ''}
              onChange={(e) => handleSentimentChange(e.target.value)}
              className="bg-transparent text-xs text-[#F5F2EA] focus:outline-none cursor-pointer"
            >
              <option value="" className="bg-[#18191B] text-[#F5F2EA]">All Sentiments</option>
              <option value="positive" className="bg-[#18191B] text-[#F5F2EA]">Positive</option>
              <option value="neutral" className="bg-[#18191B] text-[#F5F2EA]">Neutral</option>
              <option value="negative" className="bg-[#18191B] text-[#F5F2EA]">Negative</option>
            </select>
          </div>
        </div>
      </div>

      {/* Review Count Info */}
      <div className="flex items-center justify-between text-xs text-[#74736E] mb-4 px-1">
        <span>
          Showing <span className="text-[#F5F2EA] font-medium">{items.length}</span> of{' '}
          <span className="text-[#F0D58A] font-semibold">{total.toLocaleString()}</span> reviews
        </span>
        <span>Page {currentPage} of {Math.max(1, totalPages)}</span>
      </div>

      {/* Content */}
      {isLoading ? (
        <div className="py-12 text-center space-y-2">
          <Loader2 className="mx-auto h-6 w-6 animate-spin text-[#D4AF5A]" />
          <p className="text-xs text-[#AAA79F]">Loading reviews from dataset...</p>
        </div>
      ) : error ? (
        <div className="rounded-xl border border-rose-900/40 bg-rose-950/20 p-5 text-center text-xs text-rose-300">
          <p className="font-semibold">{error}</p>
          <button
            onClick={() => fetchReviews(currentPage, ratingFilter, sentimentFilter)}
            className="mt-3 text-xs text-[#D4AF5A] underline"
          >
            Retry loading reviews
          </button>
        </div>
      ) : items.length === 0 ? (
        <div className="py-10 text-center space-y-2 border border-dashed border-[#292A2B] rounded-xl">
          <p className="text-xs text-[#AAA79F]">No reviews match the selected filters.</p>
          {(ratingFilter || sentimentFilter) && (
            <button
              onClick={() => {
                setRatingFilter(undefined);
                setSentimentFilter(undefined);
                setCurrentPage(1);
              }}
              className="text-xs text-[#D4AF5A] hover:underline"
            >
              Clear filters
            </button>
          )}
        </div>
      ) : (
        <div className="space-y-3">
          {items.map((review) => {
            const isExpanded = expandedReviews[review.id];
            const isLong = review.review_text.length > 280;

            return (
              <div
                key={review.id}
                className="rounded-xl border border-[#292A2B] bg-[#18191B] p-4.5 hover:border-[#35363B] transition"
              >
                <div className="flex items-center justify-between gap-3 mb-2.5">
                  <div className="flex items-center gap-1.5">
                    {Array.from({ length: 5 }).map((_, i) => (
                      <Star
                        key={i}
                        className={`h-3.5 w-3.5 ${
                          i < review.rating
                            ? 'fill-[#D4AF5A] text-[#D4AF5A]'
                            : 'fill-transparent text-[#3A3B40]'
                        }`}
                      />
                    ))}
                    <span className="ml-1 text-xs font-semibold text-[#F5F2EA]">
                      {review.rating}.0
                    </span>
                  </div>

                  <span
                    className={`rounded px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${
                      review.sentiment === 'positive'
                        ? 'bg-emerald-950/60 text-emerald-400 border border-emerald-500/30'
                        : review.sentiment === 'negative'
                        ? 'bg-rose-950/60 text-rose-400 border border-rose-500/30'
                        : 'bg-amber-950/60 text-amber-400 border border-amber-500/30'
                    }`}
                  >
                    {review.sentiment}
                  </span>
                </div>

                <p
                  className={`text-xs text-[#E5E1D8] leading-relaxed ${
                    !isExpanded && isLong ? 'line-clamp-3' : ''
                  }`}
                >
                  "{review.review_text}"
                </p>

                {isLong && (
                  <button
                    onClick={() => toggleExpand(review.id)}
                    className="mt-1 text-[11px] font-medium text-[#D4AF5A] hover:underline"
                  >
                    {isExpanded ? 'Show less' : 'Read full review'}
                  </button>
                )}

                <div className="mt-3 pt-2 border-t border-[#222325] flex items-center justify-between text-[10px] text-[#74736E]">
                  <span className="font-mono">Review ID: #{review.id}</span>
                  <span>Dataset Verified</span>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Pagination Bar */}
      {totalPages > 1 && (
        <div className="mt-6 pt-4 border-t border-[#242526] flex items-center justify-between">
          <button
            onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
            disabled={currentPage <= 1 || isLoading}
            className="flex items-center gap-1.5 rounded-lg border border-[#292A2B] bg-[#161719] px-3.5 py-2 text-xs font-medium text-[#AAA79F] transition hover:border-[#D4AF5A]/40 hover:text-[#F5F2EA] disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <ChevronLeft className="h-3.5 w-3.5" />
            Previous
          </button>

          <span className="text-xs text-[#AAA79F] font-mono">
            Page {currentPage} of {totalPages}
          </span>

          <button
            onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
            disabled={currentPage >= totalPages || isLoading}
            className="flex items-center gap-1.5 rounded-lg border border-[#292A2B] bg-[#161719] px-3.5 py-2 text-xs font-medium text-[#AAA79F] transition hover:border-[#D4AF5A]/40 hover:text-[#F5F2EA] disabled:opacity-40 disabled:cursor-not-allowed"
          >
            Next
            <ChevronRight className="h-3.5 w-3.5" />
          </button>
        </div>
      )}
    </div>
  );
};
