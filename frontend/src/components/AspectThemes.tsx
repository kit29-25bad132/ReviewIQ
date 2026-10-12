import React from 'react';
import { Layers, Quote } from 'lucide-react';
import { AspectResult } from '../types/intelligence';

interface AspectThemesProps {
  aspects: AspectResult[];
}

const SENTIMENT_STYLES: Record<AspectResult['sentiment'], string> = {
  positive: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  negative: 'bg-rose-50 text-rose-700 border-rose-200',
  mixed: 'bg-amber-50 text-amber-700 border-amber-200',
};

/**
 * Recurring aspects with the mention count the backend counted over real
 * reviews and a verbatim citation. Each card links to nothing invented: the
 * quote and the review id come straight from the payload.
 */
export const AspectThemes: React.FC<AspectThemesProps> = ({ aspects }) => {
  if (!aspects.length) {
    return null;
  }

  return (
    <div className="modern-card p-6 space-y-4">
      <div className="flex items-center justify-between border-b border-slate-100 pb-3">
        <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
          <Layers className="h-4 w-4 text-indigo-600" />
          Recurring Themes &amp; Aspects
        </h3>
        <span className="text-xs text-slate-400">{aspects.length} themes</span>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {aspects.map((aspect) => (
          <div
            key={aspect.aspect_name}
            className="rounded-xl border border-slate-200 bg-white p-4 space-y-2 shadow-2xs"
          >
            <div className="flex items-start justify-between gap-2">
              <span className="text-xs font-bold text-slate-900 capitalize">
                {aspect.aspect_name}
              </span>
              <span
                className={`shrink-0 rounded-full border px-2 py-0.5 text-[10px] font-bold uppercase ${SENTIMENT_STYLES[aspect.sentiment]}`}
              >
                {aspect.sentiment}
              </span>
            </div>

            <div className="text-[11px] text-slate-500 font-medium">
              Mentioned in {aspect.mention_count} {aspect.mention_count === 1 ? 'review' : 'reviews'}
            </div>

            <div className="flex items-start gap-1.5 rounded-lg bg-slate-50 p-2">
              <Quote className="h-3 w-3 text-slate-400 shrink-0 mt-0.5" />
              <p className="text-[11px] text-slate-600 italic leading-snug">
                {aspect.representative_quote.excerpt}
                <span className="ml-1 not-italic font-mono text-[10px] text-slate-400">
                  [{aspect.representative_quote.review_id}]
                </span>
              </p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
