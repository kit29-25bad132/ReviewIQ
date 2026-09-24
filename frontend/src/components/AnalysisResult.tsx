import React, { useState } from 'react';
import {
  CheckCircle2,
  XCircle,
  Star,
  FileText,
  Copy,
  Check,
  Code2,
  ThumbsUp,
  ThumbsDown,
  MinusCircle,
  Scale,
} from 'lucide-react';
import { PointEvidence, ReviewAnalysis } from '../types/review';

interface AnalysisResultProps {
  analysis: ReviewAnalysis;
  originalText?: string;
}

const renderPointEvidenceList = (
  items: PointEvidence[],
  tone: 'emerald' | 'rose'
) => {
  const isPros = tone === 'emerald';
  return (
    <ul className="space-y-2.5 flex-1">
      {items.map((item, index) => (
        <li
          key={index}
          className={`flex items-start gap-2.5 rounded-lg border p-2.5 text-xs sm:text-sm text-slate-200 transition-all ${
            isPros
              ? 'border-emerald-500/15 bg-emerald-900/20 hover:border-emerald-500/30'
              : 'border-rose-500/15 bg-rose-900/20 hover:border-rose-500/30'
          }`}
        >
          <span
            className={`font-bold shrink-0 ${isPros ? 'text-emerald-400' : 'text-rose-400'}`}
          >
            {isPros ? '✓' : '✗'}
          </span>
          <span className="flex flex-col gap-1 min-w-0">
            <span>{item.point}</span>
            {item.evidence && (
              <span
                className={`text-[11px] leading-snug italic ${
                  isPros ? 'text-emerald-200/60' : 'text-rose-200/60'
                }`}
              >
                Evidence: “{item.evidence}”
              </span>
            )}
          </span>
        </li>
      ))}
    </ul>
  );
};

export const AnalysisResult: React.FC<AnalysisResultProps> = ({
  analysis,
  originalText,
}) => {
  const [copied, setCopied] = useState(false);
  const [showJson, setShowJson] = useState(false);

  const handleCopyJson = async () => {
    try {
      await navigator.clipboard.writeText(JSON.stringify(analysis, null, 2));
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback
    }
  };

  // Render sentiment configuration
  const renderSentimentBadge = () => {
    switch (analysis.sentiment) {
      case 'positive':
        return (
          <div className="inline-flex items-center gap-2 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-3.5 py-1.5 text-sm font-semibold text-emerald-400 shadow-[0_0_15px_rgba(16,185,129,0.2)]">
            <span className="text-base leading-none">🟢</span>
            <ThumbsUp className="h-4 w-4" />
            <span className="capitalize">Positive Sentiment</span>
          </div>
        );
      case 'negative':
        return (
          <div className="inline-flex items-center gap-2 rounded-full border border-rose-500/30 bg-rose-500/10 px-3.5 py-1.5 text-sm font-semibold text-rose-400 shadow-[0_0_15px_rgba(244,63,94,0.2)]">
            <span className="text-base leading-none">🔴</span>
            <ThumbsDown className="h-4 w-4" />
            <span className="capitalize">Negative Sentiment</span>
          </div>
        );
      case 'mixed':
        return (
          <div className="inline-flex items-center gap-2 rounded-full border border-violet-500/30 bg-violet-500/10 px-3.5 py-1.5 text-sm font-semibold text-violet-300 shadow-[0_0_15px_rgba(139,92,246,0.2)]">
            <span className="text-base leading-none">🟣</span>
            <Scale className="h-4 w-4" />
            <span className="capitalize">Mixed Sentiment</span>
          </div>
        );
      case 'neutral':
      default:
        return (
          <div className="inline-flex items-center gap-2 rounded-full border border-amber-500/30 bg-amber-500/10 px-3.5 py-1.5 text-sm font-semibold text-amber-400 shadow-[0_0_15px_rgba(245,158,11,0.2)]">
            <span className="text-base leading-none">🟡</span>
            <MinusCircle className="h-4 w-4" />
            <span className="capitalize">Neutral Sentiment</span>
          </div>
        );
    }
  };

  // Render 5 stars matching the exact integer rating
  const renderStars = (rating: number) => {
    const clampedRating = Math.max(1, Math.min(5, Math.round(rating)));
    return (
      <div className="flex items-center gap-1">
        {[1, 2, 3, 4, 5].map((starIdx) => {
          const isFilled = starIdx <= clampedRating;
          return (
            <Star
              key={starIdx}
              className={`h-5 w-5 ${
                isFilled
                  ? 'fill-amber-400 text-amber-400 filter drop-shadow-[0_0_6px_rgba(245,158,11,0.5)]'
                  : 'text-slate-600'
              }`}
            />
          );
        })}
      </div>
    );
  };

  const ratingSourceLabel = (source: ReviewAnalysis['rating_source']) => {
    switch (source) {
      case 'explicit':
        return 'Explicit rating';
      case 'inferred':
        return 'Inferred rating';
      case 'not_found':
        return 'Rating not found';
      default:
        return null;
    }
  };

  return (
    <div className="relative overflow-hidden rounded-2xl border border-purple-500/30 bg-[#111827]/90 p-6 sm:p-7 backdrop-blur-xl shadow-glass transition-all duration-300">
      {/* Top action header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-5">
        <div className="flex flex-wrap items-center gap-3">
          {renderSentimentBadge()}
          {analysis.rating !== null ? (
            <div className="flex items-center gap-2.5 rounded-full border border-slate-700 bg-slate-800/80 px-3.5 py-1.5 text-sm">
              {renderStars(analysis.rating)}
              <span className="font-mono font-bold text-white">
                {analysis.rating} / 5
              </span>
              {ratingSourceLabel(analysis.rating_source) && (
                <span className="text-[10px] uppercase tracking-wide text-slate-400 border-l border-slate-700 pl-2">
                  {ratingSourceLabel(analysis.rating_source)}
                </span>
              )}
            </div>
          ) : (
            <div className="flex items-center gap-2 rounded-full border border-slate-700 bg-slate-800/80 px-3.5 py-1.5 text-sm text-slate-400">
              <Star className="h-4 w-4 text-slate-600" />
              <span className="font-mono font-semibold">No rating</span>
              <span className="text-[10px] uppercase tracking-wide border-l border-slate-700 pl-2">
                {ratingSourceLabel(analysis.rating_source) ?? 'Rating not found'}
              </span>
            </div>
          )}
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setShowJson(!showJson)}
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-700 bg-slate-800/60 px-3 py-1.5 text-xs font-medium text-slate-300 hover:bg-slate-700 hover:text-white transition"
            title="Toggle Raw JSON View"
          >
            <Code2 className="h-3.5 w-3.5" />
            {showJson ? 'Hide JSON' : 'View JSON'}
          </button>
          <button
            type="button"
            onClick={handleCopyJson}
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-700 bg-slate-800/60 px-3 py-1.5 text-xs font-medium text-slate-300 hover:bg-slate-700 hover:text-white transition"
            title="Copy Structured JSON"
          >
            {copied ? (
              <>
                <Check className="h-3.5 w-3.5 text-emerald-400" />
                <span className="text-emerald-400">Copied</span>
              </>
            ) : (
              <>
                <Copy className="h-3.5 w-3.5" />
                <span>Copy JSON</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Raw JSON toggle preview */}
      {showJson && (
        <div className="mt-5 rounded-xl border border-slate-700 bg-[#0B0F17] p-4 text-xs font-mono text-purple-300 overflow-x-auto">
          <pre>{JSON.stringify(analysis, null, 2)}</pre>
        </div>
      )}

      {/* Main Content Sections: Pros & Cons */}
      <div className="mt-6 grid grid-cols-1 md:grid-cols-2 gap-5">
        {/* Pros Card */}
        <div className="flex flex-col rounded-xl border border-emerald-500/20 bg-emerald-950/20 p-4 sm:p-5 backdrop-blur-sm">
          <div className="flex items-center gap-2 text-emerald-400 font-semibold text-sm mb-3">
            <CheckCircle2 className="h-4 w-4" />
            <span>Pros & Strengths</span>
            <span className="ml-auto rounded-full bg-emerald-500/20 px-2 py-0.5 text-xs font-mono text-emerald-300">
              {analysis.pros.length}
            </span>
          </div>

          {analysis.pros.length > 0 ? (
            renderPointEvidenceList(analysis.pros, 'emerald')
          ) : (
            <div className="flex flex-1 items-center justify-center rounded-lg border border-dashed border-emerald-900/40 p-4 text-xs text-slate-400 italic">
              No clear pros mentioned in review
            </div>
          )}
        </div>

        {/* Cons Card */}
        <div className="flex flex-col rounded-xl border border-rose-500/20 bg-rose-950/20 p-4 sm:p-5 backdrop-blur-sm">
          <div className="flex items-center gap-2 text-rose-400 font-semibold text-sm mb-3">
            <XCircle className="h-4 w-4" />
            <span>Cons & Pain Points</span>
            <span className="ml-auto rounded-full bg-rose-500/20 px-2 py-0.5 text-xs font-mono text-rose-300">
              {analysis.cons.length}
            </span>
          </div>

          {analysis.cons.length > 0 ? (
            renderPointEvidenceList(analysis.cons, 'rose')
          ) : (
            <div className="flex flex-1 items-center justify-center rounded-lg border border-dashed border-rose-900/40 p-4 text-xs text-slate-400 italic">
              No clear cons mentioned in review
            </div>
          )}
        </div>
      </div>

      {/* Aspect sentiments (contract field; shown when present) */}
      {analysis.aspects.length > 0 && (
        <div className="mt-5 rounded-xl border border-cyan-500/20 bg-cyan-950/20 p-4 sm:p-5 backdrop-blur-sm">
          <div className="flex items-center gap-2 text-cyan-300 font-semibold text-sm mb-2">
            <FileText className="h-4 w-4 text-cyan-400" />
            <span>Aspect Sentiments</span>
            <span className="ml-auto rounded-full bg-cyan-500/20 px-2 py-0.5 text-xs font-mono text-cyan-200">
              {analysis.aspects.length}
            </span>
          </div>
          <ul className="space-y-2">
            {analysis.aspects.map((aspect, index) => (
              <li
                key={index}
                className="rounded-lg border border-cyan-500/15 bg-cyan-900/20 p-2.5 text-xs sm:text-sm text-slate-200"
              >
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-semibold text-cyan-200 capitalize">
                    {aspect.aspect}
                  </span>
                  <span
                    className={`rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${
                      aspect.sentiment === 'positive'
                        ? 'bg-emerald-500/15 text-emerald-300'
                        : aspect.sentiment === 'negative'
                          ? 'bg-rose-500/15 text-rose-300'
                          : aspect.sentiment === 'mixed'
                            ? 'bg-violet-500/15 text-violet-300'
                            : 'bg-amber-500/15 text-amber-300'
                    }`}
                  >
                    {aspect.sentiment}
                  </span>
                </div>
                {aspect.evidence && (
                  <p className="mt-1 text-[11px] italic text-slate-400">
                    Evidence: “{aspect.evidence}”
                  </p>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* AI Summary Section */}
      <div className="mt-5 rounded-xl border border-purple-500/20 bg-purple-950/20 p-4 sm:p-5 backdrop-blur-sm">
        <div className="flex items-center gap-2 text-purple-300 font-semibold text-sm mb-2">
          <FileText className="h-4 w-4 text-purple-400" />
          <span>AI Executive Summary</span>
        </div>
        <p className="text-sm leading-relaxed text-slate-200">
          {analysis.summary}
        </p>
      </div>

      {/* Optional original text expandable reference */}
      {originalText && (
        <details className="mt-4 group text-xs">
          <summary className="cursor-pointer text-slate-400 hover:text-slate-200 transition font-medium">
            View Analyzed Customer Text
          </summary>
          <div className="mt-2 rounded-lg border border-slate-800 bg-[#0B0F17]/80 p-3 text-slate-400 italic">
            "{originalText}"
          </div>
        </details>
      )}
    </div>
  );
};
