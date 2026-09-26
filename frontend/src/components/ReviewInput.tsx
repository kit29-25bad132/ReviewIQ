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
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      e.preventDefault();
      if (!isEmpty && !isOverLimit && !isLoading) {
        handleSubmit();
      }
    }
  };

  return (
    <div className="premium-panel p-6 sm:p-8 space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-[#292A2B] pb-4">
        <div>
          <h2 className="text-base font-medium text-[#F5F2EA] flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-[#D4AF5A]" />
            Direct Review AI Analyzer
          </h2>
          <p className="text-xs text-[#74736E] mt-0.5">
            Paste unstructured feedback to extract structured insights and ratings using Google Gemini.
          </p>
        </div>

        <div className="flex items-center gap-2">
          {review && (
            <button
              type="button"
              onClick={handleClear}
              disabled={isLoading}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-[#292A2B] bg-[#151617] text-xs text-[#AAA79F] hover:text-[#F5F2EA] transition disabled:opacity-50"
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
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-[#D4AF5A]/30 bg-[#1B1915] text-xs font-medium text-[#D4AF5A] hover:border-[#D4AF5A]/60 transition disabled:opacity-50"
          >
            <Wand2 className="h-3.5 w-3.5 text-[#D4AF5A]" />
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
          className="w-full rounded-xl border border-[#292A2B] bg-[#151617] p-4 text-sm text-[#F5F2EA] placeholder-[#74736E] focus:border-[#D4AF5A]/60 focus:outline-none focus:ring-2 focus:ring-[#D4AF5A]/20 disabled:opacity-60 transition duration-200 resize-y min-h-[140px]"
          aria-label="Customer product review text"
        />
      </div>

      {/* Footer controls: counter & submit */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pt-2">
        <div className="flex items-center gap-2 text-xs font-mono">
          <span className={isOverLimit ? 'text-rose-400 font-bold' : 'text-[#74736E]'}>
            {charCount.toLocaleString()} / {MAX_CHAR_COUNT.toLocaleString()} chars
          </span>
          {isOverLimit && (
            <span className="text-rose-400 text-xs font-sans">
              (Exceeds character limit)
            </span>
          )}
        </div>

        <button
          type="button"
          onClick={() => handleSubmit()}
          disabled={isEmpty || isOverLimit || isLoading}
          className="gold-button inline-flex items-center justify-center gap-2 px-6 py-2.5 text-xs font-semibold disabled:cursor-not-allowed disabled:opacity-50"
        >
          {isLoading ? (
            <>
              <div className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-[#111] border-t-transparent" />
              <span>Analyzing with Gemini...</span>
            </>
          ) : (
            <>
              <Send className="h-3.5 w-3.5" />
              <span>Analyze Review</span>
            </>
          )}
        </button>
      </div>

      {/* Error alert */}
      {errorMessage && (
        <div className="flex items-start gap-3 rounded-xl border border-rose-900/40 bg-rose-950/20 p-3.5 text-rose-300 text-xs">
          <AlertCircle className="h-4 w-4 shrink-0 text-rose-400 mt-0.5" />
          <div className="flex-1 font-medium">{errorMessage}</div>
        </div>
      )}
    </div>
  );
};
