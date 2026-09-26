import React, { useState } from 'react';
import {
  History,
  Trash2,
  ExternalLink,
  Search,
  Calendar,
  AlertTriangle,
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
  storageSource = 'local',
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

  return (
    <div className="premium-panel p-6 sm:p-8 space-y-6">
      {/* Header with Search and Clear Controls */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-[#292A2B] pb-5">
        <div>
          <div className="flex items-center gap-2.5">
            <h2 className="text-lg font-medium text-[#F5F2EA] flex items-center gap-2">
              <History className="h-4 w-4 text-[#D4AF5A]" />
              Analysis History
            </h2>
            <span
              className={`rounded-full border px-2.5 py-0.5 text-[10px] font-mono ${
                storageSource === 'supabase'
                  ? 'border-emerald-800/40 bg-emerald-950/40 text-emerald-400'
                  : 'border-[#292A2B] bg-[#151617] text-[#AAA79F]'
              }`}
            >
              {storageSource === 'supabase' ? 'Supabase Synced' : 'Local Storage'}
            </span>
          </div>
          <p className="text-xs text-[#74736E] mt-1">
            {history.length} saved review assessments
          </p>
        </div>

        {history.length > 0 && (
          <div className="flex flex-wrap items-center gap-3">
            {/* Search Input */}
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-[#74736E]" />
              <input
                type="text"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                placeholder="Search history..."
                className="w-44 sm:w-56 rounded-xl border border-[#292A2B] bg-[#151617] py-1.5 pl-9 pr-3 text-xs text-[#F5F2EA] placeholder-[#74736E] focus:border-[#D4AF5A]/60 focus:outline-none"
              />
            </div>

            {/* Sentiment Filter */}
            <div className="flex items-center gap-1 rounded-xl border border-[#292A2B] bg-[#151617] p-1">
              {(['all', 'positive', 'neutral', 'negative', 'mixed'] as const).map((sent) => (
                <button
                  key={sent}
                  onClick={() => setSentimentFilter(sent)}
                  className={`rounded-lg px-2.5 py-1 text-[11px] capitalize transition ${
                    sentimentFilter === sent
                      ? 'bg-[#1B1915] border border-[#D4AF5A]/40 text-[#F0D58A] font-medium'
                      : 'text-[#AAA79F] hover:text-[#F5F2EA]'
                  }`}
                >
                  {sent}
                </button>
              ))}
            </div>

            {/* Clear all */}
            <button
              onClick={() => setShowConfirmClear(true)}
              className="inline-flex items-center gap-1.5 rounded-xl border border-rose-900/40 bg-rose-950/20 px-3 py-1.5 text-xs text-rose-300 hover:bg-rose-900/30 transition"
              title="Clear all saved history"
            >
              <Trash2 className="h-3.5 w-3.5" />
              <span>Clear</span>
            </button>
          </div>
        )}
      </div>

      {/* Confirm Clear Modal Dialog */}
      {showConfirmClear && (
        <div className="rounded-xl border border-rose-900/60 bg-rose-950/40 p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center gap-2.5 text-xs text-rose-200">
            <AlertTriangle className="h-4 w-4 text-rose-400 shrink-0" />
            <span>Are you sure you want to delete all {history.length} history records?</span>
          </div>
          <div className="flex items-center gap-2 self-end sm:self-center">
            <button
              onClick={() => setShowConfirmClear(false)}
              className="rounded-lg border border-[#292A2B] bg-[#151617] px-3 py-1 text-xs text-[#AAA79F] hover:text-[#F5F2EA]"
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
              Yes, Clear All
            </button>
          </div>
        </div>
      )}

      {/* History Items List */}
      {history.length === 0 ? (
        <div className="rounded-xl border border-dashed border-[#292A2B] bg-[#151617]/40 p-12 text-center space-y-2">
          <History className="h-8 w-8 text-[#74736E] mx-auto" />
          <p className="text-sm font-medium text-[#F5F2EA]">No analysis history yet</p>
          <p className="text-xs text-[#74736E]">
            Analyzed reviews will be saved and listed here for quick access.
          </p>
        </div>
      ) : filteredHistory.length === 0 ? (
        <div className="rounded-xl border border-dashed border-[#292A2B] bg-[#151617]/40 p-8 text-center text-xs text-[#74736E]">
          No history items match your search filter "{searchTerm}".
        </div>
      ) : (
        <div className="space-y-3">
          {filteredHistory.map((item) => (
            <div
              key={item.id}
              className="rounded-xl border border-[#292A2B] bg-[#151617] p-4 transition hover:border-[#D4AF5A]/30 space-y-3"
            >
              <div className="flex items-start justify-between gap-4">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span
                      className={`rounded px-2 py-0.5 text-[10px] font-semibold uppercase ${
                        item.analysis.sentiment === 'positive'
                          ? 'border border-emerald-800/40 bg-emerald-950/40 text-emerald-400'
                          : item.analysis.sentiment === 'negative'
                          ? 'border border-rose-800/40 bg-rose-950/40 text-rose-400'
                          : 'border border-[#D4AF5A]/40 bg-[#1B1915] text-[#D4AF5A]'
                      }`}
                    >
                      {item.analysis.sentiment}
                    </span>

                    {item.analysis.rating !== null && (
                      <span className="text-xs font-semibold text-[#D4AF5A]">
                        ★ {item.analysis.rating}/5
                      </span>
                    )}

                    <span className="text-[11px] text-[#74736E] flex items-center gap-1 font-mono">
                      <Calendar className="h-3 w-3" />
                      {formatDate(item.createdAt)}
                    </span>
                  </div>

                  <p className="text-xs sm:text-sm text-[#F5F2EA] leading-relaxed line-clamp-2">
                    {item.analysis.summary || item.reviewText}
                  </p>
                </div>

                <div className="flex items-center gap-1 shrink-0">
                  <button
                    onClick={() => {
                      if (onSelectReview) onSelectReview(item);
                      setSelectedModalItem(item);
                    }}
                    className="inline-flex items-center gap-1 rounded-lg border border-[#292A2B] bg-[#111213] px-2.5 py-1.5 text-xs text-[#D4AF5A] hover:border-[#D4AF5A]/40 hover:bg-[#1C1D1F] transition"
                  >
                    <ExternalLink className="h-3 w-3" />
                    <span>Inspect</span>
                  </button>

                  <button
                    onClick={() => onDeleteReview(item.id)}
                    className="rounded-lg p-1.5 text-[#74736E] hover:bg-rose-950/30 hover:text-rose-400 transition"
                    title="Delete item"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>

              {/* Snippet stats */}
              <div className="flex items-center gap-4 text-[11px] text-[#74736E] pt-2 border-t border-[#292A2B]/60">
                <span>Pros: {item.analysis.pros.length}</span>
                <span>Cons: {item.analysis.cons.length}</span>
                <span>Aspects: {item.analysis.aspects.length}</span>
                <span className="truncate max-w-xs italic text-[#AAA79F]">"{item.reviewText.slice(0, 60)}..."</span>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Inspect Review Detail Modal */}
      {selectedModalItem && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
          <div className="relative max-h-[85vh] w-full max-w-3xl overflow-y-auto rounded-2xl border border-[#292A2B] bg-[#111213] shadow-2xl p-6 space-y-6">
            <div className="flex items-center justify-between border-b border-[#292A2B] pb-4">
              <div>
                <h3 className="text-base font-medium text-[#F5F2EA] flex items-center gap-2">
                  <Sparkles className="h-4 w-4 text-[#D4AF5A]" />
                  Saved Review Analysis
                </h3>
                <p className="text-xs text-[#74736E] mt-0.5">
                  Saved on {formatDate(selectedModalItem.createdAt)}
                </p>
              </div>

              <button
                onClick={() => setSelectedModalItem(null)}
                className="rounded-lg p-1.5 text-[#74736E] hover:bg-[#1C1D1F] hover:text-[#F5F2EA] transition"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            {/* Original review */}
            <div className="rounded-xl border border-[#292A2B] bg-[#151617] p-4 space-y-1.5">
              <span className="text-[10px] uppercase tracking-wider text-[#74736E] font-medium">Original Review Text</span>
              <p className="text-xs sm:text-sm text-[#F5F2EA] leading-relaxed italic">
                "{selectedModalItem.reviewText}"
              </p>
            </div>

            {/* Structured Result */}
            <AnalysisResult
              analysis={selectedModalItem.analysis}
            />

            <div className="pt-4 border-t border-[#292A2B] text-right">
              <button
                onClick={() => setSelectedModalItem(null)}
                className="rounded-lg border border-[#292A2B] bg-[#151617] px-5 py-2 text-xs text-[#F5F2EA] hover:bg-[#1C1D1F] transition"
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
