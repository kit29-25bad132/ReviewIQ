import React, { useEffect, useState } from 'react';
import { ShieldCheck, Star, Search, Loader2, Quote } from 'lucide-react';
import { ReviewItem } from '../types/ecommerce';
import { getThemeSupportingReviews } from '../services/api';

interface EvidenceViewerProps {
  productId: string;
  selectedTheme?: string | null;
  selectedSentiment?: 'positive' | 'negative' | null;
  initialReviews?: ReviewItem[];
  onClearTheme?: () => void;
}

export const EvidenceViewer: React.FC<EvidenceViewerProps> = ({
  productId,
  selectedTheme,
  selectedSentiment,
  initialReviews = [],
  onClearTheme,
}) => {
  const [reviews, setReviews] = useState<ReviewItem[]>(initialReviews);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filterQuery, setFilterQuery] = useState('');

  // Fetch theme-specific supporting reviews whenever selectedTheme changes
  useEffect(() => {
    if (!selectedTheme) {
      setReviews(initialReviews);
      setError(null);
      return;
    }

    let isCurrent = true;
    setIsLoading(true);
    setError(null);

    getThemeSupportingReviews(productId, selectedTheme, selectedSentiment || undefined, 40)
      .then((data) => {
        if (isCurrent) {
          setReviews(data);
          setIsLoading(false);
        }
      })
      .catch((err) => {
        if (isCurrent) {
          setError(
            err instanceof Error ? err.message : 'Failed to retrieve supporting reviews for this theme.'
          );
          setIsLoading(false);
        }
      });

    return () => {
      isCurrent = false;
    };
  }, [productId, selectedTheme, selectedSentiment, initialReviews]);

  const filteredReviews = reviews.filter((r) => {
    if (!filterQuery.trim()) return true;
    return r.review_text.toLowerCase().includes(filterQuery.toLowerCase());
  });

  return (
    <div className="premium-panel p-6 sm:p-7 border border-[#292A2B] bg-[#141517]">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-6 pb-5 border-b border-[#242526]">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <div className="flex h-7 w-7 items-center justify-center rounded-lg border border-[#D4AF5A]/40 bg-[#1E1B15] text-[#D4AF5A]">
              <ShieldCheck className="h-4 w-4" />
            </div>
            <h3 className="text-sm font-semibold tracking-wide text-[#F5F2EA] uppercase">
              Traceable Review Evidence
            </h3>
          </div>
          <p className="text-xs text-[#AAA79F]">
            Every AI insight is anchored to authentic customer reviews from the dataset
          </p>
        </div>

        {/* Selected Theme Badge / Filter */}
        <div className="flex flex-wrap items-center gap-2">
          {selectedTheme ? (
            <div className="flex items-center gap-2 rounded-lg border border-[#D4AF5A]/40 bg-[#201D17] px-3 py-1.5 text-xs">
              <span className="text-[#AAA79F]">Filtered by theme:</span>
              <span className="font-semibold text-[#F0D58A]">{selectedTheme}</span>
              {selectedSentiment && (
                <span
                  className={`rounded px-1.5 py-0.2 text-[10px] uppercase font-bold ${
                    selectedSentiment === 'positive'
                      ? 'bg-emerald-950/60 text-emerald-400'
                      : 'bg-rose-950/60 text-rose-400'
                  }`}
                >
                  {selectedSentiment}
                </span>
              )}
              {onClearTheme && (
                <button
                  onClick={onClearTheme}
                  className="ml-2 text-[#AAA79F] hover:text-[#F5F2EA] font-bold text-xs"
                  title="Show all evidence"
                >
                  ✕
                </button>
              )}
            </div>
          ) : (
            <span className="rounded-md border border-[#292A2B] bg-[#1A1B1E] px-2.5 py-1 text-xs text-[#AAA79F]">
              Click any aspect or pro/con above to isolate supporting reviews
            </span>
          )}
        </div>
      </div>

      {/* Internal Filter / Search in Evidence */}
      {reviews.length > 0 && (
        <div className="mb-5 flex items-center gap-3 rounded-lg border border-[#292A2B] bg-[#161719] px-3 py-2 text-xs focus-within:border-[#D4AF5A]/50">
          <Search className="h-3.5 w-3.5 text-[#74736E]" />
          <input
            type="text"
            value={filterQuery}
            onChange={(e) => setFilterQuery(e.target.value)}
            placeholder="Search keyword within supporting evidence text..."
            className="w-full bg-transparent text-[#F5F2EA] placeholder:text-[#74736E] focus:outline-none"
          />
          {filterQuery && (
            <button
              onClick={() => setFilterQuery('')}
              className="text-[#74736E] hover:text-[#AAA79F] text-xs font-semibold"
            >
              Clear
            </button>
          )}
        </div>
      )}

      {/* Loading state */}
      {isLoading ? (
        <div className="py-12 text-center space-y-3">
          <Loader2 className="mx-auto h-6 w-6 animate-spin text-[#D4AF5A]" />
          <p className="text-xs text-[#AAA79F]">
            Querying dataset reviews supporting "{selectedTheme}"...
          </p>
        </div>
      ) : error ? (
        <div className="rounded-xl border border-rose-900/40 bg-rose-950/20 p-5 text-center text-xs text-rose-300">
          <p className="font-semibold">{error}</p>
          <p className="mt-1 text-rose-400/80">
            Please ensure the backend is running and the dataset is ready.
          </p>
        </div>
      ) : filteredReviews.length === 0 ? (
        <div className="py-10 text-center space-y-2 border border-dashed border-[#292A2B] rounded-xl">
          <Quote className="mx-auto h-6 w-6 text-[#74736E]" />
          <p className="text-xs font-medium text-[#AAA79F]">
            {filterQuery
              ? `No evidence reviews match "${filterQuery}".`
              : 'No supporting reviews found for this specific criterion.'}
          </p>
          {selectedTheme && onClearTheme && (
            <button
              onClick={onClearTheme}
              className="text-xs text-[#D4AF5A] hover:underline pt-2 block mx-auto"
            >
              Reset theme filter
            </button>
          )}
        </div>
      ) : (
        <div className="space-y-3">
          <div className="flex items-center justify-between text-[11px] text-[#74736E] px-1">
            <span>
              Showing {filteredReviews.length} verified review{filteredReviews.length === 1 ? '' : 's'}
            </span>
            {selectedTheme && (
              <span className="text-[#D4AF5A] font-medium">
                Direct evidence for: {selectedTheme}
              </span>
            )}
          </div>

          <div className="grid gap-3 sm:grid-cols-1 md:grid-cols-2">
            {filteredReviews.map((review) => (
              <div
                key={review.id}
                className="rounded-xl border border-[#292A2B] bg-[#17181A] p-4 flex flex-col justify-between hover:border-[#383A40] transition"
              >
                <div>
                  <div className="flex items-center justify-between gap-2 mb-2 pb-2 border-b border-[#242526]">
                    {/* Star Rating */}
                    <div className="flex items-center gap-1">
                      {Array.from({ length: 5 }).map((_, i) => (
                        <Star
                          key={i}
                          className={`h-3 w-3 ${
                            i < review.rating
                              ? 'fill-[#D4AF5A] text-[#D4AF5A]'
                              : 'fill-transparent text-[#3A3B40]'
                          }`}
                        />
                      ))}
                      <span className="ml-1 text-[11px] font-bold text-[#F5F2EA]">
                        {review.rating}.0
                      </span>
                    </div>

                    {/* Sentiment Tag */}
                    <span
                      className={`rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${
                        review.sentiment === 'positive'
                          ? 'bg-emerald-950/60 text-emerald-400 border border-emerald-500/20'
                          : review.sentiment === 'negative'
                          ? 'bg-rose-950/60 text-rose-400 border border-rose-500/20'
                          : 'bg-amber-950/60 text-amber-400 border border-amber-500/20'
                      }`}
                    >
                      {review.sentiment}
                    </span>
                  </div>

                  {/* Review Text */}
                  <p className="text-xs text-[#E5E1D8] leading-relaxed line-clamp-4">
                    "{review.review_text}"
                  </p>
                </div>

                {/* Footer metadata */}
                <div className="mt-4 pt-2 border-t border-[#222325] flex items-center justify-between text-[10px] text-[#74736E]">
                  <span className="font-mono">Review ID: #{review.id}</span>
                  <span className="text-[#AAA79F]">Verified Dataset Source</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
