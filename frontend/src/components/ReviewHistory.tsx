import React, { useState } from 'react';
import {
  History,
  Trash2,
  ExternalLink,
  Search,
  Filter,
  Calendar,
  AlertTriangle,
  X,
} from 'lucide-react';
import { ReviewHistoryItem } from '../types/review';
import { AnalysisResult } from './AnalysisResult';

interface ReviewHistoryProps {
  history: ReviewHistoryItem[];
  onSelectReview: (item: ReviewHistoryItem) => void;
  onDeleteReview: (id: string) => void;
  onClearHistory: () => void;
}

export const ReviewHistory: React.FC<ReviewHistoryProps> = ({
  history,
  onSelectReview,
  onDeleteReview,
  onClearHistory,
}) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [sentimentFilter, setSentimentFilter] = useState<
    'all' | 'positive' | 'negative' | 'neutral' | 'mixed'
  >('all');
  const [selectedModalItem, setSelectedModalItem] = useState<ReviewHistoryItem | null>(null);
  const [showConfirmClear, setShowConfirmClear] = useState(false);

  // Filter history items
  const filteredHistory = history.filter((item) => {
    const pointText = (entries: { point: string; evidence: string }[]) =>
      entries.some(
        (entry) =>
          entry.point.toLowerCase().includes(searchTerm.toLowerCase()) ||
          entry.evidence.toLowerCase().includes(searchTerm.toLowerCase())
      );

    const matchesSearch =
      item.reviewText.toLowerCase().includes(searchTerm.toLowerCase()) ||
      item.analysis.summary.toLowerCase().includes(searchTerm.toLowerCase()) ||
      pointText(item.analysis.pros) ||
      pointText(item.analysis.cons);

    const matchesSentiment =
      sentimentFilter === 'all' || item.analysis.sentiment === sentimentFilter;

    return matchesSearch && matchesSentiment;
  });

  const formatDate = (isoString: string) => {
    try {
      const date = new Date(isoString);
      return new Intl.DateTimeFormat('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      }).format(date);
    } catch {
      return isoString;
    }
  };

  const getSentimentDot = (sentiment: string) => {
    switch (sentiment) {
      case 'positive':
        return <span title="Positive">🟢</span>;
      case 'negative':
        return <span title="Negative">🔴</span>;
      case 'mixed':
        return <span title="Mixed">🟣</span>;
      case 'neutral':
      default:
        return <span title="Neutral">🟡</span>;
    }
  };

  return (
    <div className="relative overflow-hidden rounded-2xl border border-white/10 bg-[#111827]/80 p-6 backdrop-blur-xl shadow-glass">
      {/* Header with Search and Clear Controls */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800 pb-5">
        <div>
          <h2 className="text-lg font-bold text-white flex items-center gap-2">
            <History className="h-5 w-5 text-purple-400" />
            Analysis History
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Locally saved review assessments ({history.length} total)
          </p>
        </div>

        {history.length > 0 && (
          <div className="flex flex-wrap items-center gap-3">
            {/* Search Input */}
            <div className="relative min-w-[200px]">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-slate-400" />
              <input
                type="text"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                placeholder="Search history..."
                className="w-full rounded-lg border border-slate-700 bg-[#0B0F17] py-1.5 pl-8 pr-3 text-xs text-slate-200 placeholder-slate-500 focus:border-purple-500 focus:outline-none"
              />
            </div>

            {/* Sentiment filter */}
            <div className="flex items-center gap-1.5 rounded-lg border border-slate-700 bg-[#0B0F17] p-1 text-xs">
              <Filter className="h-3 w-3 text-slate-400 ml-1.5" />
              <select
                value={sentimentFilter}
                onChange={(e) => setSentimentFilter(e.target.value as any)}
                className="bg-transparent text-slate-300 focus:outline-none pr-1 cursor-pointer"
              >
                <option value="all" className="bg-[#111827]">All</option>
                <option value="positive" className="bg-[#111827]">Positive</option>
                <option value="neutral" className="bg-[#111827]">Neutral</option>
                <option value="negative" className="bg-[#111827]">Negative</option>
                <option value="mixed" className="bg-[#111827]">Mixed</option>
              </select>
            </div>

            {/* Clear button */}
            <button
              type="button"
              onClick={() => setShowConfirmClear(true)}
              className="inline-flex items-center gap-1.5 rounded-lg border border-rose-500/20 bg-rose-500/10 px-3 py-1.5 text-xs font-medium text-rose-300 hover:bg-rose-500/20 transition"
              title="Clear all history"
            >
              <Trash2 className="h-3.5 w-3.5" />
              Clear History
            </button>
          </div>
        )}
      </div>

      {/* Confirmation Modal for Clearing History */}
      {showConfirmClear && (
        <div className="mt-4 rounded-xl border border-rose-500/40 bg-rose-950/40 p-4 backdrop-blur-md flex flex-col sm:flex-row items-center justify-between gap-3">
          <div className="flex items-center gap-2 text-rose-300 text-xs">
            <AlertTriangle className="h-4 w-4 shrink-0 text-rose-400" />
            <span>Are you sure you want to delete all saved review analyses? This action cannot be undone.</span>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <button
              onClick={() => setShowConfirmClear(false)}
              className="rounded-lg border border-slate-700 bg-slate-800 px-3 py-1 text-xs text-slate-300 hover:text-white"
            >
              Cancel
            </button>
            <button
              onClick={() => {
                onClearHistory();
                setShowConfirmClear(false);
              }}
              className="rounded-lg bg-rose-600 px-3 py-1 text-xs font-semibold text-white hover:bg-rose-500"
            >
              Confirm Clear
            </button>
          </div>
        </div>
      )}

      {/* History Items or Empty State */}
      <div className="mt-5 space-y-3">
        {history.length === 0 ? (
          <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-slate-800 py-12 px-4 text-center">
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-slate-800/80 text-slate-400 mb-3">
              <History className="h-6 w-6" />
            </div>
            <h3 className="text-sm font-semibold text-slate-200">No reviews analyzed yet.</h3>
            <p className="mt-1 text-xs text-slate-400 max-w-sm">
              Analyze your first customer review to see insights, pros/cons, and rating metrics here.
            </p>
          </div>
        ) : filteredHistory.length === 0 ? (
          <div className="py-8 text-center text-xs text-slate-400">
            No reviews matching your search filter.
          </div>
        ) : (
          filteredHistory.map((item) => (
            <div
              key={item.id}
              className="group relative flex flex-col sm:flex-row sm:items-center justify-between gap-4 rounded-xl border border-slate-800 bg-[#0B0F17]/80 p-4 transition-all hover:border-purple-500/30 hover:bg-[#111827]"
            >
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1.5 flex-wrap">
                  <span className="text-sm leading-none">{getSentimentDot(item.analysis.sentiment)}</span>
                  <span className="text-xs font-semibold capitalize text-slate-200">
                    {item.analysis.sentiment}
                  </span>
                  <span className="text-slate-600">•</span>
                  <span className="text-xs font-mono font-bold text-amber-400">
                    {item.analysis.rating !== null
                      ? `${'★'.repeat(item.analysis.rating)}${'☆'.repeat(5 - item.analysis.rating)} (${item.analysis.rating}/5)`
                      : 'No rating'}
                  </span>
                  <span className="text-slate-600">•</span>
                  <span className="flex items-center gap-1 text-[11px] text-slate-400">
                    <Calendar className="h-3 w-3" />
                    {formatDate(item.createdAt)}
                  </span>
                </div>

                {/* Review excerpt */}
                <p className="text-xs text-slate-300 line-clamp-2 leading-relaxed">
                  "{item.reviewText}"
                </p>

                {/* Summary badge */}
                <p className="mt-1 text-[11px] text-purple-400 line-clamp-1 italic">
                  Summary: {item.analysis.summary}
                </p>
              </div>

              {/* Action Buttons */}
              <div className="flex items-center gap-2 shrink-0 self-end sm:self-center">
                <button
                  type="button"
                  onClick={() => setSelectedModalItem(item)}
                  className="inline-flex items-center gap-1 rounded-lg border border-purple-500/20 bg-purple-500/10 px-2.5 py-1.5 text-xs font-medium text-purple-300 hover:bg-purple-500/20 transition"
                  title="View full report"
                >
                  <ExternalLink className="h-3.5 w-3.5" />
                  <span>View</span>
                </button>
                <button
                  type="button"
                  onClick={() => onSelectReview(item)}
                  className="inline-flex items-center gap-1 rounded-lg border border-slate-700 bg-slate-800/80 px-2.5 py-1.5 text-xs font-medium text-slate-300 hover:bg-slate-700 transition"
                  title="Load into active analyzer"
                >
                  <span>Load</span>
                </button>
                <button
                  type="button"
                  onClick={() => onDeleteReview(item.id)}
                  className="inline-flex items-center justify-center rounded-lg p-1.5 text-slate-400 hover:bg-rose-500/20 hover:text-rose-400 transition"
                  title="Delete review"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            </div>
          ))
        )}
      </div>

      {/* Modal Dialog to View Full Past Analysis */}
      {selectedModalItem && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm animate-fadeIn">
          <div className="relative w-full max-w-2xl max-h-[90vh] overflow-y-auto rounded-2xl border border-purple-500/30 bg-[#0B0F17] p-6 shadow-2xl">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3 mb-4">
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <History className="h-4 w-4 text-purple-400" />
                Historical Analysis Detail
              </h3>
              <button
                type="button"
                onClick={() => setSelectedModalItem(null)}
                className="rounded-lg p-1 text-slate-400 hover:bg-slate-800 hover:text-white transition"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <AnalysisResult
              analysis={selectedModalItem.analysis}
              originalText={selectedModalItem.reviewText}
            />

            <div className="mt-5 flex justify-end">
              <button
                type="button"
                onClick={() => setSelectedModalItem(null)}
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
