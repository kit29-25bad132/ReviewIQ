import React, { useState } from 'react';
import {
  History,
  Trash2,
  ExternalLink,
  Search,
  Calendar,
  X,
  Sparkles,
} from 'lucide-react';
import { ReviewHistoryItem } from '../types/review';
import { AnalysisResult } from './AnalysisResult';

interface ReviewHistoryProps {
  history: ReviewHistoryItem[];
  onSelectReview?: (item: ReviewHistoryItem) => void;
  onDeleteReview: (id: string) => void;
  onClearHistory: () => void;
  storageSource?: 'supabase' | 'local';
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

  return (
    <div className="modern-card p-6 sm:p-8 space-y-6">
      {/* Header with Search and Clear Controls */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-100 pb-5">
        <div>
          <h2 className="text-lg font-bold text-slate-900 flex items-center gap-2">
            <History className="h-5 w-5 text-indigo-600" />
            <span>Analysis History</span>
          </h2>
          <p className="text-xs text-slate-500 mt-1">
            {history.length} saved review assessments
          </p>
        </div>

        {history.length > 0 && (
          <div className="flex flex-wrap items-center gap-3">
            {/* Search Input */}
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-slate-400" />
              <input
                type="text"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                placeholder="Search history..."
                className="w-44 sm:w-56 rounded-xl border border-slate-200 bg-white py-1.5 pl-9 pr-3 text-xs text-slate-900 placeholder-slate-400 focus:border-indigo-500 focus:outline-none"
              />
            </div>

            {/* Sentiment Filter */}
            <div className="flex items-center gap-1 rounded-xl border border-slate-200 bg-slate-50 p-1">
              {(['all', 'positive', 'neutral', 'negative', 'mixed'] as const).map((sent) => (
                <button
                  key={sent}
                  onClick={() => setSentimentFilter(sent)}
                  className={`rounded-lg px-2.5 py-1 text-[11px] font-bold capitalize transition ${
                    sentimentFilter === sent
                      ? 'bg-white text-indigo-600 shadow-xs'
                      : 'text-slate-500 hover:text-slate-900'
                  }`}
                >
                  {sent}
                </button>
              ))}
            </div>

            {/* Clear all */}
            <button
              onClick={onClearHistory}
              className="inline-flex items-center gap-1.5 rounded-xl border border-rose-200 bg-rose-50 px-3 py-1.5 text-xs font-bold text-rose-700 hover:bg-rose-100 transition cursor-pointer"
              title="Clear all saved history"
            >
              <Trash2 className="h-3.5 w-3.5" />
              <span>Clear</span>
            </button>
          </div>
        )}
      </div>

      {/* History Items List */}
      {history.length === 0 ? (
        <div className="rounded-xl border border-dashed border-slate-200 p-12 text-center space-y-2">
          <History className="h-8 w-8 text-slate-400 mx-auto" />
          <p className="text-sm font-bold text-slate-800">No analysis history yet</p>
          <p className="text-xs text-slate-500">
            Analyzed reviews will be saved and listed here for quick access.
          </p>
        </div>
      ) : filteredHistory.length === 0 ? (
        <div className="rounded-xl border border-dashed border-slate-200 p-8 text-center text-xs text-slate-500">
          No history items match your search filter "{searchTerm}".
        </div>
      ) : (
        <div className="space-y-3">
          {filteredHistory.map((item) => (
            <div
              key={item.id}
              className="rounded-2xl border border-slate-200 bg-white p-4 transition hover:border-indigo-200 hover:shadow-xs space-y-3"
            >
              <div className="flex items-start justify-between gap-4">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span
                      className={`rounded-full px-2.5 py-0.5 text-[10px] font-bold uppercase ${
                        item.analysis.sentiment === 'positive'
                          ? 'border border-emerald-200 bg-emerald-50 text-emerald-700'
                          : item.analysis.sentiment === 'negative'
                          ? 'border border-rose-200 bg-rose-50 text-rose-700'
                          : 'border border-amber-200 bg-amber-50 text-amber-700'
                      }`}
                    >
                      {item.analysis.sentiment}
                    </span>

                    {item.analysis.rating !== null && (
                      <span className="text-xs font-bold text-amber-600">
                        ★ {item.analysis.rating}/5
                      </span>
                    )}

                    <span className="text-[11px] text-slate-400 flex items-center gap-1 font-mono">
                      <Calendar className="h-3 w-3" />
                      {formatDate(item.createdAt)}
                    </span>
                  </div>

                  <p className="text-xs sm:text-sm text-slate-800 leading-relaxed line-clamp-2 font-medium">
                    {item.analysis.summary || item.reviewText}
                  </p>
                </div>

                <div className="flex items-center gap-1 shrink-0">
                  <button
                    onClick={() => {
                      if (onSelectReview) onSelectReview(item);
                      setSelectedModalItem(item);
                    }}
                    className="inline-flex items-center gap-1 rounded-lg border border-indigo-200 bg-indigo-50 px-2.5 py-1.5 text-xs font-bold text-indigo-600 hover:bg-indigo-600 hover:text-white transition"
                  >
                    <ExternalLink className="h-3 w-3" />
                    <span>Inspect</span>
                  </button>

                  <button
                    onClick={() => onDeleteReview(item.id)}
                    className="rounded-lg p-1.5 text-slate-400 hover:bg-rose-50 hover:text-rose-600 transition"
                    title="Delete item"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>

              {/* Snippet stats */}
              <div className="flex items-center gap-4 text-[11px] text-slate-500 pt-2 border-t border-slate-100">
                <span>Pros: {item.analysis.pros.length}</span>
                <span>Cons: {item.analysis.cons.length}</span>
                <span>Aspects: {item.analysis.aspects.length}</span>
                <span className="truncate max-w-xs italic text-slate-400">"{item.reviewText.slice(0, 60)}..."</span>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Inspect Review Detail Modal */}
      {selectedModalItem && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-xs p-4 animate-fadeIn">
          <div className="relative max-h-[85vh] w-full max-w-3xl overflow-y-auto rounded-2xl border border-slate-200 bg-white shadow-2xl p-6 space-y-6">
            <div className="flex items-center justify-between border-b border-slate-100 pb-4">
              <div>
                <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
                  <Sparkles className="h-4 w-4 text-indigo-600" />
                  <span>Saved Review Analysis</span>
                </h3>
                <p className="text-xs text-slate-400 mt-0.5">
                  Saved on {formatDate(selectedModalItem.createdAt)}
                </p>
              </div>

              <button
                onClick={() => setSelectedModalItem(null)}
                className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700 transition"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            {/* Original review */}
            <div className="rounded-xl border border-slate-200 bg-slate-50/80 p-4 space-y-1.5">
              <span className="text-[10px] uppercase tracking-wider text-slate-500 font-bold">Original Review Text</span>
              <p className="text-xs sm:text-sm text-slate-800 leading-relaxed italic">
                "{selectedModalItem.reviewText}"
              </p>
            </div>

            {/* Structured Result */}
            <AnalysisResult
              analysis={selectedModalItem.analysis}
            />

            <div className="pt-4 border-t border-slate-100 text-right">
              <button
                onClick={() => setSelectedModalItem(null)}
                className="rounded-xl bg-slate-800 px-5 py-2 text-xs font-bold text-white hover:bg-slate-900 transition"
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
