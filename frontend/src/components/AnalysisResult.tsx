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
  Sparkles,
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
          className={`flex items-start gap-2.5 rounded-lg border p-3 text-xs sm:text-sm text-[#F5F2EA] transition-all ${
            isPros
              ? 'border-emerald-800/40 bg-emerald-950/20 hover:border-emerald-700/60'
              : 'border-rose-800/40 bg-rose-950/20 hover:border-rose-700/60'
          }`}
        >
          <span
            className={`font-bold shrink-0 ${isPros ? 'text-emerald-400' : 'text-rose-400'}`}
          >
            {isPros ? '✓' : '✗'}
          </span>
          <span className="flex flex-col gap-1 min-w-0">
            <span className="font-medium">{item.point}</span>
            {item.evidence && (
              <span
                className={`text-[11px] leading-snug italic ${
                  isPros ? 'text-emerald-300/70' : 'text-rose-300/70'
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

  const renderSentimentBadge = () => {
    switch (analysis.sentiment) {
      case 'positive':
        return (
          <div className="inline-flex items-center gap-2 rounded-full border border-emerald-800/50 bg-emerald-950/40 px-3.5 py-1.5 text-xs font-semibold text-emerald-400">
            <ThumbsUp className="h-4 w-4" />
            <span className="capitalize">Positive Sentiment</span>
          </div>
        );
      case 'negative':
        return (
          <div className="inline-flex items-center gap-2 rounded-full border border-rose-800/50 bg-rose-950/40 px-3.5 py-1.5 text-xs font-semibold text-rose-400">
            <ThumbsDown className="h-4 w-4" />
            <span className="capitalize">Negative Sentiment</span>
          </div>
        );
      case 'mixed':
        return (
          <div className="inline-flex items-center gap-2 rounded-full border border-[#D4AF5A]/40 bg-[#1B1915] px-3.5 py-1.5 text-xs font-semibold text-[#F0D58A]">
            <Scale className="h-4 w-4" />
            <span className="capitalize">Mixed Sentiment</span>
          </div>
        );
      case 'neutral':
      default:
        return (
          <div className="inline-flex items-center gap-2 rounded-full border border-[#292A2B] bg-[#151617] px-3.5 py-1.5 text-xs font-semibold text-[#AAA79F]">
            <MinusCircle className="h-4 w-4" />
            <span className="capitalize">Neutral Sentiment</span>
          </div>
        );
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Banner: Sentiment & Stars Card */}
      <div className="premium-panel p-6 relative overflow-hidden">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-5">
          {/* Sentiment & Rating Badge */}
          <div className="flex flex-wrap items-center gap-4">
            {renderSentimentBadge()}

            {analysis.rating !== null ? (
              <div className="flex items-center gap-2 rounded-xl border border-[#292A2B] bg-[#151617] px-4 py-2">
                <div className="flex items-center text-[#D4AF5A]">
                  {[1, 2, 3, 4, 5].map((star) => (
                    <Star
                      key={star}
                      className={`h-4 w-4 ${
                        star <= (analysis.rating || 0)
                          ? 'fill-[#D4AF5A] text-[#D4AF5A]'
                          : 'text-[#292A2B]'
                      }`}
                    />
                  ))}
                </div>
                <span className="text-sm font-semibold text-[#D4AF5A]">
                  {analysis.rating} / 5
                </span>
                <span className="text-[10px] text-[#74736E] uppercase font-mono">
                  ({analysis.rating_source || 'inferred'})
                </span>
              </div>
            ) : (
              <span className="text-xs text-[#74736E]">No explicit rating</span>
            )}
          </div>

          {/* Action Tools: JSON View & Copy */}
          <div className="flex items-center gap-2 self-end sm:self-center">
            <button
              onClick={() => setShowJson(!showJson)}
              className="inline-flex items-center gap-1.5 rounded-lg border border-[#292A2B] bg-[#151617] px-3 py-1.5 text-xs text-[#AAA79F] hover:border-[#D4AF5A]/30 hover:text-[#F5F2EA] transition"
            >
              <Code2 className="h-3.5 w-3.5 text-[#D4AF5A]" />
              <span>{showJson ? 'Hide JSON' : 'View JSON'}</span>
            </button>
            <button
              onClick={handleCopyJson}
              className="inline-flex items-center gap-1.5 rounded-lg border border-[#292A2B] bg-[#151617] px-3 py-1.5 text-xs text-[#AAA79F] hover:border-[#D4AF5A]/30 hover:text-[#F5F2EA] transition"
            >
              {copied ? (
                <>
                  <Check className="h-3.5 w-3.5 text-emerald-400" />
                  <span className="text-emerald-400">Copied</span>
                </>
              ) : (
                <>
                  <Copy className="h-3.5 w-3.5" />
                  <span>Copy</span>
                </>
              )}
            </button>
          </div>
        </div>

        {/* JSON Output Viewer Drawer */}
        {showJson && (
          <div className="mt-4 rounded-xl border border-[#292A2B] bg-[#0E0F10] p-4 text-xs font-mono text-[#AAA79F] overflow-x-auto">
            <pre>{JSON.stringify(analysis, null, 2)}</pre>
          </div>
        )}
      </div>

      {/* Executive Summary */}
      <div className="premium-panel p-6 space-y-3">
        <h3 className="text-xs uppercase tracking-wider font-semibold text-[#D4AF5A] flex items-center gap-2">
          <FileText className="h-4 w-4" />
          Executive Summary
        </h3>
        <p className="text-sm leading-relaxed text-[#F5F2EA]">
          {analysis.summary}
        </p>
      </div>

      {/* Aspects Analysis Breakdown */}
      {analysis.aspects && analysis.aspects.length > 0 && (
        <div className="premium-panel p-6 space-y-4">
          <h3 className="text-xs uppercase tracking-wider font-semibold text-[#D4AF5A] flex items-center gap-2">
            <Sparkles className="h-4 w-4" />
            Aspect-Level Sentiment & Evidence
          </h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {analysis.aspects.map((aspect, i) => {
              const isPos = aspect.sentiment === 'positive';
              const isNeg = aspect.sentiment === 'negative';
              return (
                <div
                  key={i}
                  className="rounded-xl border border-[#292A2B] bg-[#151617] p-4 space-y-2 text-xs"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-semibold text-[#F5F2EA] uppercase tracking-wide">
                      {aspect.aspect}
                    </span>
                    <span className="flex items-center gap-1.5 shrink-0">
                      {aspect.support && (
                        <span
                          title="Deterministic evidence support (application-computed, not a model confidence score)"
                          className={`rounded px-2 py-0.5 text-[10px] font-mono uppercase ${
                            aspect.support === 'strong'
                              ? 'border border-emerald-800/40 bg-emerald-950/30 text-emerald-300'
                              : aspect.support === 'moderate'
                              ? 'border border-[#D4AF5A]/40 bg-[#1B1915] text-[#F0D58A]'
                              : 'border border-[#292A2B] bg-[#111213] text-[#AAA79F]'
                          }`}
                        >
                          {aspect.support} support
                        </span>
                      )}
                      <span
                        className={`rounded px-2 py-0.5 text-[10px] font-semibold uppercase ${
                          isPos
                            ? 'border border-emerald-800/40 bg-emerald-950/40 text-emerald-400'
                            : isNeg
                            ? 'border border-rose-800/40 bg-rose-950/40 text-rose-400'
                            : 'border border-[#292A2B] bg-[#111213] text-[#AAA79F]'
                        }`}
                      >
                        {aspect.sentiment}
                      </span>
                    </span>
                  </div>
                  {aspect.evidence && (
                    <p className="text-[11px] italic text-[#74736E] leading-snug">
                      "{aspect.evidence}"
                    </p>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Pros & Cons with Evidence Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
        {/* Pros */}
        <div className="premium-panel p-6 space-y-4">
          <div className="flex items-center gap-2 text-emerald-400 border-b border-[#292A2B] pb-3 text-sm font-semibold">
            <CheckCircle2 className="h-4 w-4" />
            <span>Identified Strengths ({analysis.pros.length})</span>
          </div>
          {analysis.pros.length > 0 ? (
            renderPointEvidenceList(analysis.pros, 'emerald')
          ) : (
            <p className="text-xs text-[#74736E] italic">No explicit pros identified in this review.</p>
          )}
        </div>

        {/* Cons */}
        <div className="premium-panel p-6 space-y-4">
          <div className="flex items-center gap-2 text-rose-400 border-b border-[#292A2B] pb-3 text-sm font-semibold">
            <XCircle className="h-4 w-4" />
            <span>Identified Pain Points ({analysis.cons.length})</span>
          </div>
          {analysis.cons.length > 0 ? (
            renderPointEvidenceList(analysis.cons, 'rose')
          ) : (
            <p className="text-xs text-[#74736E] italic">No explicit cons identified in this review.</p>
          )}
        </div>
      </div>
    </div>
  );
};
