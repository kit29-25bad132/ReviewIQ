import React, { useState } from 'react';
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
    <div className="premium-panel p-6 space-y-5">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-[#292A2B] pb-4">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="text-base font-medium text-[#F5F2EA] flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-[#D4AF5A]" />
              AI Review Intelligence & Synthesis
            </h3>
            <span className="rounded-full border border-[#D4AF5A]/30 bg-[#1B1915] px-2.5 py-0.5 text-[10px] font-mono text-[#D4AF5A]">
              Gemini AI
            </span>
          </div>
          <p className="text-xs text-[#74736E] mt-1 flex items-center gap-1.5">
            <ShieldCheck className="h-3.5 w-3.5 text-[#D4AF5A]" />
            <span>Summary constrained strictly to dataset reviews</span>
          </p>
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
          <p className="text-xs text-[#AAA79F]">Synthesizing dataset reviews with Gemini AI...</p>
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
