import React, { useState, useEffect } from 'react';
import {
  Sparkles,
  CheckCircle2,
  XCircle,
  Tag,
  RefreshCw,
  ShieldCheck,
  FileText,
  AlertCircle,
} from 'lucide-react';
import { AISummaryResponse } from '../types/ecommerce';
import { generateAISummary } from '../services/api';

interface AISummaryCardProps {
  productId: string;
  initialSummary?: AISummaryResponse | null;
}

export const AISummaryCard: React.FC<AISummaryCardProps> = ({
  productId,
  initialSummary,
}) => {
  const [summary, setSummary] = useState<AISummaryResponse | null>(initialSummary || null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string>('');

  useEffect(() => {
    let isMounted = true;
    if (initialSummary) {
      setSummary(initialSummary);
      setLoading(false);
      setError('');
      return;
    }

    setLoading(true);
    setError('');
    generateAISummary(productId)
      .then((res) => {
        if (isMounted) {
          setSummary(res);
          setError('');
        }
      })
      .catch((err: unknown) => {
        if (isMounted) {
          const msg = err instanceof Error ? err.message : 'Unable to generate AI summary.';
          setError(msg);
        }
      })
      .finally(() => {
        if (isMounted) setLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [productId, initialSummary]);

  const handleGenerate = async () => {
    setLoading(true);
    setError('');
    try {
      const res = await generateAISummary(productId);
      setSummary(res);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Unable to generate AI summary.';
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modern-card p-6 sm:p-8 space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-100 pb-4">
        <div>
          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-indigo-50 text-indigo-600">
              <Sparkles className="h-4 w-4" />
            </div>
            <h3 className="text-base font-bold text-slate-900">
              AI Review Intelligence & Synthesis
            </h3>
            <span className="rounded-full bg-indigo-50 border border-indigo-100 px-2.5 py-0.5 text-[10px] font-semibold text-indigo-700">
              Gemini AI
            </span>
          </div>
          <p className="text-xs text-slate-500 mt-1 flex items-center gap-1.5">
            <ShieldCheck className="h-3.5 w-3.5 text-emerald-600" />
            <span>Summary constrained strictly to verified dataset reviews</span>
          </p>
        </div>

        <button
          onClick={handleGenerate}
          disabled={loading}
          className="primary-button inline-flex items-center gap-1.5 px-4 py-2 text-xs font-semibold shrink-0"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
          <span>{summary ? 'Regenerate AI Summary' : 'Generate AI Summary'}</span>
        </button>
      </div>

      {loading ? (
        <div className="py-12 text-center space-y-3">
          <div className="inline-block h-8 w-8 animate-spin rounded-full border-2 border-indigo-600 border-t-transparent" />
          <p className="text-xs text-slate-500 font-medium">Synthesizing dataset reviews with Gemini AI...</p>
        </div>
      ) : error ? (
        <div className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-xs text-rose-700 flex items-center gap-2">
          <AlertCircle className="h-4 w-4 text-rose-600 shrink-0" />
          <span>{error}</span>
        </div>
      ) : !summary ? (
        <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50/50 p-8 text-center space-y-2">
          <FileText className="h-7 w-7 text-slate-400 mx-auto" />
          <p className="text-sm text-slate-800 font-semibold">No AI summary generated yet for this product.</p>
          <p className="text-xs text-slate-500 max-w-md mx-auto">
            Click <strong className="text-indigo-600">"Generate AI Summary"</strong> above to synthesize the customer reviews into structured themes, pros, and cons.
          </p>
        </div>
      ) : (
        <div className="space-y-6">
          {/* Summary paragraph */}
          <div className="rounded-2xl bg-indigo-50/40 border border-indigo-100/80 p-5 text-sm text-slate-700 leading-relaxed font-normal">
            {summary.summary}
          </div>

          {/* Key Themes Chips */}
          {summary.key_themes && summary.key_themes.length > 0 && (
            <div className="space-y-2">
              <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-1">
                <Tag className="h-3.5 w-3.5 text-indigo-500" />
                Key Themes Extracted
              </span>
              <div className="flex flex-wrap items-center gap-2">
                {summary.key_themes.map((theme, i) => (
                  <span
                    key={i}
                    className="rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 shadow-xs"
                  >
                    {theme}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Pros & Cons list in summary */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2">
            {/* Pros */}
            {summary.common_pros && summary.common_pros.length > 0 && (
              <div className="rounded-2xl border border-emerald-100 bg-emerald-50/40 p-5 space-y-3">
                <h4 className="text-xs font-bold text-emerald-900 flex items-center gap-1.5">
                  <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                  Key Strengths
                </h4>
                <ul className="space-y-2">
                  {summary.common_pros.map((pro, i) => (
                    <li key={i} className="text-xs text-emerald-800 flex items-start gap-2">
                      <span className="text-emerald-500 font-bold">•</span>
                      <span>{pro}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Cons */}
            {summary.common_cons && summary.common_cons.length > 0 && (
              <div className="rounded-2xl border border-rose-100 bg-rose-50/40 p-5 space-y-3">
                <h4 className="text-xs font-bold text-rose-900 flex items-center gap-1.5">
                  <XCircle className="h-4 w-4 text-rose-600" />
                  Common Complaints
                </h4>
                <ul className="space-y-2">
                  {summary.common_cons.map((con, i) => (
                    <li key={i} className="text-xs text-rose-800 flex items-start gap-2">
                      <span className="text-rose-500 font-bold">•</span>
                      <span>{con}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
