import React from 'react';
import { Sparkles, AlertCircle, Target, Info } from 'lucide-react';
import { ProductIntelligence } from '../types/intelligence';

interface IntelligenceSummaryProps {
  intelligence: ProductIntelligence;
}

/**
 * Renders the AI summary and the "best for" line from the API payload.
 *
 * When the backend reports ai_unavailable or low_review_count, that is shown
 * plainly rather than hidden — the statistics above remain real and complete.
 */
export const IntelligenceSummary: React.FC<IntelligenceSummaryProps> = ({ intelligence }) => {
  const { summary, best_for, ai_unavailable, low_review_count, review_count_used } = intelligence;

  return (
    <div className="modern-card p-6 space-y-5">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-100 pb-4">
        <div className="flex items-center gap-2">
          <Sparkles className="h-5 w-5 text-indigo-600" />
          <h3 className="text-base font-bold text-slate-900">AI Product Intelligence</h3>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <span className="rounded-full border border-indigo-100 bg-indigo-50 px-3 py-1 text-[11px] font-semibold text-indigo-700">
            Grounded in {review_count_used.toLocaleString()} reviews
          </span>
          {low_review_count && (
            <span className="inline-flex items-center gap-1 rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-[11px] font-bold text-amber-800">
              <Info className="h-3.5 w-3.5" />
              Low review count
            </span>
          )}
        </div>
      </div>

      {ai_unavailable ? (
        <div className="flex items-start gap-3 rounded-2xl border border-amber-200 bg-amber-50 p-4">
          <AlertCircle className="h-5 w-5 text-amber-600 shrink-0 mt-0.5" />
          <div className="space-y-1">
            <p className="text-xs font-bold text-amber-900">AI analysis unavailable</p>
            <p className="text-xs text-amber-800 leading-relaxed">
              The statistics above are complete and computed directly from the database, but the
              AI summary could not be generated. No AI content is shown rather than showing
              unverified content.
            </p>
          </div>
        </div>
      ) : (
        <>
          <div className="rounded-2xl border border-indigo-100 bg-indigo-50/40 p-4">
            <p className="text-xs sm:text-sm text-slate-800 leading-relaxed font-medium">
              {summary}
            </p>
          </div>

          {best_for && (
            <div className="flex items-start gap-3 rounded-2xl border border-emerald-100 bg-emerald-50/50 p-4">
              <Target className="h-4 w-4 text-emerald-600 shrink-0 mt-0.5" />
              <div>
                <p className="text-[11px] font-bold uppercase tracking-wider text-emerald-700">
                  Best for
                </p>
                <p className="text-xs sm:text-sm text-slate-800 font-medium mt-0.5">{best_for}</p>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
};
