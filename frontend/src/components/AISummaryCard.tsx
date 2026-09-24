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
    } catch (err: any) {
      setError(
        err.response?.data?.detail ||
          err.message ||
          'Unable to generate AI summary. Verify GEMINI_API_KEY in backend/.env'
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="relative overflow-hidden rounded-2xl border border-purple-500/30 bg-[#111827]/90 p-6 backdrop-blur-xl shadow-glass space-y-5">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-4">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="text-base font-bold text-white flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-purple-400" />
              AI Review Intelligence & Synthesis
            </h3>
            <span className="rounded-full bg-purple-500/20 border border-purple-500/30 px-2 py-0.5 text-[10px] font-mono text-purple-300">
              Gemini AI
            </span>
          </div>
          <p className="text-[11px] font-mono text-cyan-300 mt-1 flex items-center gap-1">
            <ShieldCheck className="h-3.5 w-3.5 text-cyan-400" />
            <span>Summary generated strictly from dataset reviews</span>
          </p>
        </div>

        <button
          onClick={handleGenerate}
          disabled={loading}
          className="inline-flex items-center gap-1.5 rounded-xl border border-purple-500/40 bg-purple-500/15 px-3.5 py-1.5 text-xs font-semibold text-purple-200 hover:bg-purple-500/25 transition disabled:opacity-50 shrink-0"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin text-purple-400' : ''}`} />
          <span>{summary ? 'Regenerate AI Summary' : 'Generate AI Summary'}</span>
        </button>
      </div>

      {loading ? (
        <div className="py-8 text-center space-y-2">
          <div className="inline-block h-6 w-6 animate-spin rounded-full border-2 border-purple-400 border-t-transparent" />
          <p className="text-xs text-slate-400 font-mono">Synthesizing dataset reviews with Gemini AI...</p>
        </div>
      ) : error ? (
        <div className="rounded-xl border border-rose-500/30 bg-rose-500/10 p-4 text-xs text-rose-300 flex items-center gap-2">
          <AlertCircle className="h-4 w-4 text-rose-400 shrink-0" />
          <span>{error}</span>
        </div>
      ) : !summary ? (
        <div className="rounded-xl border border-dashed border-slate-800 p-6 text-center space-y-2">
          <FileText className="h-6 w-6 text-slate-500 mx-auto" />
          <p className="text-xs text-slate-300 font-medium">No AI summary generated yet for this product.</p>
          <p className="text-[11px] text-slate-500">
            Click <strong className="text-purple-300">"Generate AI Summary"</strong> above to synthesize the customer reviews into structured pros, cons, and key themes.
          </p>
        </div>
      ) : (
        <div className="space-y-5 animate-fadeIn">
          {/* Summary paragraph */}
          <div className="rounded-xl border border-slate-800 bg-[#0B0F17]/80 p-4 text-sm text-slate-200 leading-relaxed">
            {summary.summary}
          </div>

          {/* Key Themes Chips */}
          {summary.key_themes && summary.key_themes.length > 0 && (
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-xs text-slate-400 font-mono flex items-center gap-1 mr-1">
                <Tag className="h-3 w-3 text-cyan-400" /> Key Themes:
              </span>
              {summary.key_themes.map((theme, i) => (
                <span
                  key={i}
                  className="rounded-lg border border-slate-800 bg-slate-900 px-2.5 py-1 text-xs font-medium text-slate-300"
                >
                  {theme}
                </span>
              ))}
            </div>
          )}

          {/* Pros and Cons Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {/* Pros */}
            <div className="rounded-xl border border-emerald-500/20 bg-emerald-950/20 p-4 space-y-2.5">
              <div className="flex items-center gap-1.5 text-xs font-bold text-emerald-400">
                <CheckCircle2 className="h-4 w-4" />
                <span>Common Pros (from reviews)</span>
              </div>
              {summary.common_pros.length > 0 ? (
                <ul className="space-y-1.5 text-xs text-slate-300">
                  {summary.common_pros.map((pro, idx) => (
                    <li key={idx} className="flex items-start gap-2">
                      <span className="text-emerald-400 font-bold">✓</span>
                      <span>{pro}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-xs text-slate-500 italic">No clear recurring pros noted</p>
              )}
            </div>

            {/* Cons */}
            <div className="rounded-xl border border-rose-500/20 bg-rose-950/20 p-4 space-y-2.5">
              <div className="flex items-center gap-1.5 text-xs font-bold text-rose-400">
                <XCircle className="h-4 w-4" />
                <span>Common Cons (from reviews)</span>
              </div>
              {summary.common_cons.length > 0 ? (
                <ul className="space-y-1.5 text-xs text-slate-300">
                  {summary.common_cons.map((con, idx) => (
                    <li key={idx} className="flex items-start gap-2">
                      <span className="text-rose-400 font-bold">✗</span>
                      <span>{con}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-xs text-slate-500 italic">No clear recurring cons noted</p>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
