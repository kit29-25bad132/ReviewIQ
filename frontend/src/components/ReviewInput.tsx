import React, { useState } from 'react';
import { Sparkles, AlertCircle, Wand2, XCircle, Send } from 'lucide-react';

interface ReviewInputProps {
  onAnalyze: (review: string) => Promise<void>;
  isLoading: boolean;
  errorMessage: string | null;
  onClearError: () => void;
}

const SAMPLE_REVIEW =
  "The camera quality is excellent and the display is beautiful. Battery life is good for normal use, but the phone becomes hot while gaming. Overall I am happy with the product.";

const MAX_CHAR_COUNT = 5000;

export const ReviewInput: React.FC<ReviewInputProps> = ({
  onAnalyze,
  isLoading,
  errorMessage,
  onClearError,
}) => {
  const [review, setReview] = useState<string>('');

  const charCount = review.length;
  const isOverLimit = charCount > MAX_CHAR_COUNT;
  const isEmpty = review.trim().length === 0;

  const handleTextChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setReview(e.target.value);
    if (errorMessage) {
      onClearError();
    }
  };

  const handlePopulateSample = () => {
    setReview(SAMPLE_REVIEW);
    if (errorMessage) {
      onClearError();
    }
  };

  const handleClear = () => {
    setReview('');
    if (errorMessage) {
      onClearError();
    }
  };

  const handleSubmit = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (isEmpty || isOverLimit || isLoading) return;
    await onAnalyze(review);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    // Ctrl + Enter or Cmd + Enter shortcut
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      e.preventDefault();
      if (!isEmpty && !isOverLimit && !isLoading) {
        handleSubmit();
      }
    }
  };

  return (
    <div className="relative overflow-hidden rounded-2xl border border-white/10 bg-[#111827]/80 p-6 backdrop-blur-xl shadow-glass transition-all">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
        <div>
          <h2 className="text-lg font-bold text-white flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-purple-400" />
            Enter Customer Review
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Paste unstructured feedback to extract structured insights and ratings.
          </p>
        </div>

        <div className="flex items-center gap-2">
          {review && (
            <button
              type="button"
              onClick={handleClear}
              disabled={isLoading}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-700 bg-slate-800/60 text-xs font-medium text-slate-300 hover:bg-slate-700 hover:text-white transition disabled:opacity-50"
              title="Clear input"
            >
              <XCircle className="h-3.5 w-3.5" />
              Clear
            </button>
          )}
          <button
            type="button"
            onClick={handlePopulateSample}
            disabled={isLoading}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-purple-500/30 bg-purple-500/10 text-xs font-medium text-purple-300 hover:bg-purple-500/20 hover:border-purple-500/50 transition disabled:opacity-50"
          >
            <Wand2 className="h-3.5 w-3.5 text-purple-400" />
            Try Sample Review
          </button>
        </div>
      </div>

      {/* Textarea container */}
      <div className="relative">
        <textarea
          rows={5}
          value={review}
          onChange={handleTextChange}
          onKeyDown={handleKeyDown}
          disabled={isLoading}
          placeholder="Paste a customer product review here..."
          className="w-full rounded-xl border border-slate-700/80 bg-[#0B0F17]/90 p-4 text-sm text-slate-100 placeholder-slate-500 focus:border-purple-500 focus:outline-none focus:ring-2 focus:ring-purple-500/20 disabled:opacity-60 transition duration-200 resize-y min-h-[140px]"
          aria-label="Customer product review text"
        />
      </div>

      {/* Footer controls: counter & submit */}
      <div className="mt-3 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center gap-2 text-xs font-mono">
          <span className={isOverLimit ? 'text-rose-400 font-bold' : 'text-slate-400'}>
            {charCount.toLocaleString()} / {MAX_CHAR_COUNT.toLocaleString()}
          </span>
          {isOverLimit && (
            <span className="text-rose-400 text-xs font-sans">
              (Review exceeds 5,000 character limit)
            </span>
          )}
        </div>

        <button
          type="button"
          onClick={() => handleSubmit()}
          disabled={isEmpty || isOverLimit || isLoading}
          className="inline-flex items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-purple-600 via-purple-500 to-indigo-600 px-6 py-2.5 text-sm font-semibold text-white shadow-lg shadow-purple-500/25 transition-all duration-200 hover:shadow-purple-500/40 hover:brightness-110 active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-50 disabled:shadow-none"
        >
          {isLoading ? (
            <>
              <div className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
              <span>Analyzing Review...</span>
            </>
          ) : (
            <>
              <Send className="h-4 w-4" />
              <span>Analyze Review</span>
            </>
          )}
        </button>
      </div>

      {/* Error alert */}
      {errorMessage && (
        <div className="mt-4 flex items-start gap-3 rounded-xl border border-rose-500/30 bg-rose-500/10 p-3.5 text-rose-300 text-xs">
          <AlertCircle className="h-4 w-4 shrink-0 text-rose-400 mt-0.5" />
          <div className="flex-1 font-medium">{errorMessage}</div>
        </div>
      )}
    </div>
  );
};
