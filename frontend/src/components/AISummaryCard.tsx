import React, { useEffect, useState } from 'react';
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

/**
 * Extracts a safe, server-provided error message (FastAPI `{ detail }`)
 * from a failed request. Anything else — network failures, non-string or
 * missing detail, raw objects — falls back to a concise generic message.
 * Raw Axios objects, stack traces, and provider internals are never
 * rendered. (Gate 3)
 */
export const extractSummaryErrorMessage = (error: unknown): string => {
  const generic = 'Unable to generate an AI summary right now. Please try again.';
  if (typeof error === 'object' && error !== null) {
    const detail = (error as { response?: { data?: { detail?: unknown } } }).response
      ?.data?.detail;
    if (typeof detail === 'string' && detail.trim().length > 0) {
      return detail.trim();
    }
  }
  return generic;
};

/**
 * True when the backend returned its explicit "no reviews available" empty
 * state instead of a generated summary. Such a response must never be
 * displayed as AI-generated output. (Gate 3)
 */
export const isEmptySummaryState = (res: Pick<AISummaryResponse, 'summary'>): boolean =>
  res.summary.trim().startsWith('No customer reviews are available');

export const AISummaryCard: React.FC<AISummaryCardProps> = ({
  productId,
  initialSummary,
}) => {
  const [summary, setSummary] = useState<AISummaryResponse | null>(initialSummary || null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string>('');

  // Reset whenever the product changes so a previous product's summary or
  // error is never shown as if it belonged to the new product. (Gate 3)
  useEffect(() => {
    setSummary(initialSummary || null);
    setError('');
    setLoading(false);
  }, [productId, initialSummary]);

  const handleGenerate = async () => {
    setLoading(true);
    setError('');
    try {
      const res = await generateAISummary(productId);
      setSummary(res);
    } catch (err: unknown) {
      setError(extractSummaryErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  // A real, successfully generated (non-empty) summary exists for this card.
  // Claims of AI generation are only displayed when supported by it. (Gate 4)
  const hasGeneratedSummary = summary !== null && !isEmptySummaryState(summary);

  return (
    <div className="premium-panel p-6 space-y-5">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-[#292A2B] pb-4">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="text-base font-medium text-[#F5F2EA] flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-[#D4AF5A]" />
              AI Review Intelligence & Synthesis
            </h3>
            {hasGeneratedSummary && (
              <span className="rounded-full border border-[#D4AF5A]/30 bg-[#1B1915] px-2.5 py-0.5 text-[10px] font-mono text-[#D4AF5A]">
                AI-generated
              </span>
            )}
          </div>
          {hasGeneratedSummary && (
            <p className="text-xs text-[#74736E] mt-1 flex items-center gap-1.5">
              <ShieldCheck className="h-3.5 w-3.5 text-[#D4AF5A]" />
              <span>Summary constrained strictly to dataset reviews</span>
            </p>
          )}
        </div>

        <button
          onClick={handleGenerate}
          disabled={loading}
          className="gold-button inline-flex items-center gap-1.5 px-4 py-2 text-xs font-semibold disabled:opacity-50 shrink-0"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
          <span>{summary ? 'Regenerate AI Summary' : 'Generate AI Summary'}</span>
        </button>
      </div>

      {loading ? (
        <div className="py-8 text-center space-y-2">
          <div className="inline-block h-6 w-6 animate-spin rounded-full border-2 border-[#D4AF5A] border-t-transparent" />
          <p className="text-xs text-[#AAA79F]">Synthesizing dataset reviews with AI analysis...</p>
        </div>
      ) : error ? (
        <div className="rounded-xl border border-rose-900/40 bg-rose-950/20 p-4 text-xs text-rose-300 flex items-center gap-2">
          <AlertCircle className="h-4 w-4 text-rose-400 shrink-0" />
          <span>{error}</span>
        </div>
      ) : !summary ? (
        <div className="rounded-xl border border-dashed border-[#292A2B] bg-[#151617]/50 p-6 text-center space-y-2">
          <FileText className="h-6 w-6 text-[#74736E] mx-auto" />
          <p className="text-xs text-[#F5F2EA] font-medium">No AI summary generated yet for this product.</p>
          <p className="text-xs text-[#74736E]">
            Click <strong className="text-[#D4AF5A]">"Generate AI Summary"</strong> above to synthesize the customer reviews into structured pros, cons, and key themes.
          </p>
        </div>
      ) : isEmptySummaryState(summary) ? (
        // Explicit backend empty state: there are no source reviews, so no AI
        // summary exists. Shown as an unavailable/empty state — never as
        // generated AI output. (Gate 3)
        <div className="rounded-xl border border-dashed border-[#292A2B] bg-[#151617]/50 p-6 text-center space-y-2">
          <FileText className="h-6 w-6 text-[#74736E] mx-auto" />
          <p className="text-xs text-[#F5F2EA] font-medium">
            No customer reviews are available in the dataset for this product.
          </p>
          <p className="text-xs text-[#74736E]">
            An AI summary cannot be generated because there are no source reviews to synthesize.
          </p>
        </div>
      ) : (
        <div className="space-y-5">
          {/* Summary paragraph */}
          <div className="rounded-xl border border-[#292A2B] bg-[#151617] p-5 text-sm text-[#F5F2EA] leading-relaxed">
            {summary.summary}
          </div>

          {/* Key Themes Chips */}
          {summary.key_themes && summary.key_themes.length > 0 && (
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-xs text-[#74736E] flex items-center gap-1 mr-1">
                <Tag className="h-3 w-3 text-[#D4AF5A]" /> Key Themes:
              </span>
              {summary.key_themes.map((theme, i) => (
                <span
                  key={i}
                  className="rounded-lg border border-[#292A2B] bg-[#151617] px-2.5 py-1 text-xs text-[#AAA79F]"
                >
                  {theme}
                </span>
              ))}
            </div>
          )}

          {/* Pros and Cons Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {/* Pros */}
            <div className="rounded-xl border border-[#292A2B] bg-[#151617] p-4 space-y-2.5">
              <div className="flex items-center gap-1.5 text-xs font-semibold text-emerald-400">
                <CheckCircle2 className="h-4 w-4" />
                <span>Common Pros (from reviews)</span>
              </div>
              {summary.common_pros.length > 0 ? (
                <ul className="space-y-1.5 text-xs text-[#AAA79F]">
                  {summary.common_pros.map((pro, idx) => (
                    <li key={idx} className="flex items-start gap-2">
                      <span className="text-emerald-400 font-bold">✓</span>
                      <span>{pro}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-xs text-[#74736E] italic">No clear recurring pros noted</p>
              )}
            </div>

            {/* Cons */}
            <div className="rounded-xl border border-[#292A2B] bg-[#151617] p-4 space-y-2.5">
              <div className="flex items-center gap-1.5 text-xs font-semibold text-rose-400">
                <XCircle className="h-4 w-4" />
                <span>Common Cons (from reviews)</span>
              </div>
              {summary.common_cons.length > 0 ? (
                <ul className="space-y-1.5 text-xs text-[#AAA79F]">
                  {summary.common_cons.map((con, idx) => (
                    <li key={idx} className="flex items-start gap-2">
                      <span className="text-rose-400 font-bold">✗</span>
                      <span>{con}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-xs text-[#74736E] italic">No clear recurring cons noted</p>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
