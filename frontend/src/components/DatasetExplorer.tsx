import React, { useEffect, useState } from 'react';
import {
  Search,
  Filter,
  ChevronLeft,
  ChevronRight,
  Database,
  ThumbsUp,
  ThumbsDown,
  MinusCircle,
  Calendar,
  X,
  ExternalLink,
} from 'lucide-react';
import { DatasetReview } from '../types/review';
import { getDatasetReviews } from '../services/api';

const PAGE_SIZE = 20;

export const DatasetExplorer: React.FC = () => {
  const [rows, setRows] = useState<DatasetReview[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [search, setSearch] = useState<string>('');
  const [debouncedSearch, setDebouncedSearch] = useState<string>('');
  const [rating, setRating] = useState<number | undefined>();
  const [sentiment, setSentiment] = useState<string | undefined>();
  const [page, setPage] = useState<number>(1);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string>('');
  const [selectedReview, setSelectedReview] = useState<DatasetReview | null>(null);

  // Debounce search
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(search);
      setPage(1);
    }, 300);
    return () => clearTimeout(timer);
  }, [search]);

  // Reset page when rating or sentiment changes
  const handleRatingChange = (val: string) => {
    setRating(val ? Number(val) : undefined);
    setPage(1);
  };

  const handleSentimentChange = (val: string) => {
    setSentiment(val ? val : undefined);
    setPage(1);
  };

  // Fetch reviews from Kaggle dataset
  useEffect(() => {
    let isMounted = true;
    setLoading(true);
    setError('');

    const offset = (page - 1) * PAGE_SIZE;

    getDatasetReviews({
      limit: PAGE_SIZE,
      offset,
      search: debouncedSearch.trim() || undefined,
      rating,
      sentiment,
    })
      .then((res) => {
        if (isMounted) {
          setRows(res.items);
          setTotal(res.total);
          setError('');
        }
      })
      .catch((err) => {
        if (isMounted) {
          setError(
            err.response?.data?.detail ||
              'Review dataset could not be loaded. Please verify backend/data/amazon_review.csv.'
          );
        }
      })
      .finally(() => {
        if (isMounted) setLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [debouncedSearch, rating, sentiment, page]);

  const totalPages = Math.ceil(total / PAGE_SIZE) || 1;

  const renderSentimentBadge = (sent: string) => {
    switch (sent) {
      case 'positive':
        return (
          <span className="inline-flex items-center gap-1 rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-0.5 text-[11px] font-bold text-emerald-700">
            <ThumbsUp className="h-3 w-3" /> Positive
          </span>
        );
      case 'negative':
        return (
          <span className="inline-flex items-center gap-1 rounded-full border border-rose-200 bg-rose-50 px-2.5 py-0.5 text-[11px] font-bold text-rose-700">
            <ThumbsDown className="h-3 w-3" /> Negative
          </span>
        );
      case 'neutral':
      default:
        return (
          <span className="inline-flex items-center gap-1 rounded-full border border-amber-200 bg-amber-50 px-2.5 py-0.5 text-[11px] font-bold text-amber-700">
            <MinusCircle className="h-3 w-3" /> Neutral
          </span>
        );
    }
  };

  const renderStars = (num: number) => {
    return (
      <div className="flex items-center gap-0.5 text-amber-500 font-mono font-bold text-xs">
        <span>{'★'.repeat(num)}</span>
        <span className="text-slate-300">{'☆'.repeat(5 - num)}</span>
        <span className="text-slate-500 ml-1 font-semibold">({num}/5)</span>
      </div>
    );
  };

  return (
    <section className="modern-card p-6 space-y-6">
      {/* Header & Controls */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-100 pb-5">
        <div>
          <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
            <Database className="h-4 w-4 text-indigo-600" />
            <span>Dataset Review Explorer</span>
          </h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Explore <span className="font-semibold text-slate-800">{total.toLocaleString()}</span> real customer reviews from the verified dataset.
          </p>
        </div>

        {/* Filters and Search Bar */}
        <div className="flex flex-wrap items-center gap-3">
          {/* Search */}
          <div className="relative min-w-[240px]">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-slate-400" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search review text or ASIN..."
              className="w-full rounded-xl border border-slate-200 bg-white py-2 pl-9 pr-3 text-xs text-slate-900 placeholder-slate-400 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 transition"
            />
          </div>

          {/* Rating Filter */}
          <div className="flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-2.5 py-1.5 text-xs shadow-sm">
            <Filter className="h-3.5 w-3.5 text-slate-400" />
            <select
              value={rating ?? ''}
              onChange={(e) => handleRatingChange(e.target.value)}
              className="bg-transparent text-slate-700 font-medium focus:outline-none cursor-pointer text-xs"
            >
              <option value="">All Ratings</option>
              <option value="5">5 Stars</option>
              <option value="4">4 Stars</option>
              <option value="3">3 Stars</option>
              <option value="2">2 Stars</option>
              <option value="1">1 Star</option>
            </select>
          </div>

          {/* Sentiment Filter */}
          <div className="flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-2.5 py-1.5 text-xs shadow-sm">
            <select
              value={sentiment ?? ''}
              onChange={(e) => handleSentimentChange(e.target.value)}
              className="bg-transparent text-slate-700 font-medium focus:outline-none cursor-pointer text-xs"
            >
              <option value="">All Sentiments</option>
              <option value="positive">Positive</option>
              <option value="neutral">Neutral</option>
              <option value="negative">Negative</option>
            </select>
          </div>
        </div>
      </div>

      {/* Content Area */}
      {loading ? (
        <div className="py-16 text-center space-y-3">
          <div className="inline-block h-8 w-8 animate-spin rounded-full border-3 border-indigo-600 border-t-transparent" />
          <p className="text-xs text-slate-500 font-medium">Loading verified customer reviews...</p>
        </div>
      ) : error ? (
        <div className="rounded-xl border border-rose-200 bg-rose-50 p-5 text-center text-xs text-rose-700 space-y-1">
          <p className="font-bold">{error}</p>
          <p className="text-slate-500">Ensure backend server is online and dataset is populated.</p>
        </div>
      ) : rows.length === 0 ? (
        <div className="rounded-xl border border-dashed border-slate-200 p-12 text-center space-y-2">
          <Database className="h-8 w-8 text-slate-400 mx-auto" />
          <h3 className="text-sm font-bold text-slate-800">No reviews found</h3>
          <p className="text-xs text-slate-500">Try adjusting your search terms or filter criteria.</p>
        </div>
      ) : (
        <div className="space-y-4">
          {/* Table */}
          <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
            <table className="w-full text-left text-xs">
              <thead className="border-b border-slate-200 bg-slate-50/80 text-slate-500 font-bold uppercase text-[10px]">
                <tr>
                  <th className="p-3">Product Identifier</th>
                  <th className="p-3">Rating</th>
                  <th className="p-3">Sentiment</th>
                  <th className="p-3 min-w-[280px]">Review Content</th>
                  <th className="p-3">Date</th>
                  <th className="p-3">Helpful</th>
                  <th className="p-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {rows.map((row) => (
                  <tr
                    key={row.id}
                    className="transition hover:bg-slate-50/70 group"
                  >
                    <td className="p-3 font-semibold text-indigo-600">
                      {row.product_name || `ID: ${row.asin || '—'}`}
                    </td>
                    <td className="p-3 whitespace-nowrap">{renderStars(row.actual_rating)}</td>
                    <td className="p-3 whitespace-nowrap">{renderSentimentBadge(row.actual_sentiment)}</td>
                    <td className="p-3 text-slate-700 max-w-md">
                      <p className="line-clamp-2 leading-relaxed">
                        {row.summary && (
                          <strong className="text-slate-900 font-bold block mb-0.5">
                            {row.summary}
                          </strong>
                        )}
                        {row.review_text}
                      </p>
                    </td>
                    <td className="p-3 whitespace-nowrap text-slate-500 font-mono text-[11px]">
                      {row.review_date || '—'}
                    </td>
                    <td className="p-3 whitespace-nowrap text-slate-500 font-mono text-[11px]">
                      {row.helpful_yes != null ? `${row.helpful_yes} / ${row.total_vote ?? row.helpful_yes}` : '—'}
                    </td>
                    <td className="p-3 text-right whitespace-nowrap">
                      <button
                        onClick={() => setSelectedReview(row)}
                        className="inline-flex items-center gap-1 rounded-lg border border-slate-200 bg-white px-2.5 py-1 text-[11px] font-bold text-slate-700 hover:border-indigo-500 hover:text-indigo-600 hover:bg-indigo-50 transition shadow-2xs"
                      >
                        <ExternalLink className="h-3 w-3" />
                        <span>Inspect</span>
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination Controls */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pt-2 text-xs text-slate-500">
            <div>
              Showing <span className="text-slate-900 font-bold font-mono">{(page - 1) * PAGE_SIZE + 1}</span> to{' '}
              <span className="text-slate-900 font-bold font-mono">
                {Math.min(page * PAGE_SIZE, total)}
              </span>{' '}
              of <span className="text-slate-900 font-bold font-mono">{total.toLocaleString()}</span> reviews
            </div>

            <div className="flex items-center gap-2">
              <button
                disabled={page <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                className="inline-flex items-center gap-1 rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-xs font-bold text-slate-700 hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed transition shadow-2xs"
              >
                <ChevronLeft className="h-3.5 w-3.5" />
                Previous
              </button>
              <span className="px-2 font-mono font-medium text-slate-700">
                Page {page} of {totalPages}
              </span>
              <button
                disabled={page >= totalPages}
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                className="inline-flex items-center gap-1 rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-xs font-bold text-slate-700 hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed transition shadow-2xs"
              >
                Next
                <ChevronRight className="h-3.5 w-3.5" />
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Review Detail Modal */}
      {selectedReview && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4 backdrop-blur-xs animate-fadeIn">
          <div className="relative w-full max-w-2xl max-h-[90vh] overflow-y-auto rounded-2xl border border-slate-200 bg-white p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <div>
                <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
                  <Database className="h-4 w-4 text-indigo-600" />
                  Dataset Review Record
                </h3>
                <p className="text-xs font-semibold text-indigo-600 mt-0.5">
                  {selectedReview.product_name || `Product ID: ${selectedReview.asin || '—'}`}
                </p>
              </div>
              <button
                type="button"
                onClick={() => setSelectedReview(null)}
                className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700 transition"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            {/* Metadata Pills */}
            <div className="flex flex-wrap items-center gap-3">
              {renderSentimentBadge(selectedReview.actual_sentiment)}
              <div className="flex items-center gap-1.5 rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs">
                {renderStars(selectedReview.actual_rating)}
              </div>
              {selectedReview.review_date && (
                <div className="flex items-center gap-1.5 rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs text-slate-600">
                  <Calendar className="h-3 w-3 text-slate-400" />
                  <span>{selectedReview.review_date}</span>
                </div>
              )}
              {selectedReview.helpful_yes != null && (
                <div className="flex items-center gap-1.5 rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs text-slate-600 font-mono">
                  <span>Helpful: {selectedReview.helpful_yes} / {selectedReview.total_vote ?? selectedReview.helpful_yes}</span>
                </div>
              )}
            </div>

            {/* Headline */}
            {selectedReview.summary && (
              <div className="rounded-xl border border-indigo-100 bg-indigo-50/50 p-3.5 text-sm font-bold text-indigo-950">
                "{selectedReview.summary}"
              </div>
            )}

            {/* Full text */}
            <div className="rounded-xl border border-slate-200 bg-slate-50/70 p-4 text-sm text-slate-800 leading-relaxed max-h-60 overflow-y-auto">
              {selectedReview.review_text}
            </div>

            <div className="flex justify-end pt-2">
              <button
                type="button"
                onClick={() => setSelectedReview(null)}
                className="rounded-xl bg-indigo-600 px-4 py-2 text-xs font-bold text-white hover:bg-indigo-700 transition"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
};
