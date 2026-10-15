import React, { useState } from 'react';
import {
  CheckCircle2,
  XCircle,
  Star,
  Copy,
  Check,
  Code2,
  ThumbsUp,
  ThumbsDown,
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
          className={`flex items-start gap-2.5 rounded-xl border p-3.5 text-xs text-slate-800 transition-all ${
            isPros
              ? 'border-emerald-200 bg-emerald-50/70'
              : 'border-rose-200 bg-rose-50/70'
          }`}
        >
          <span
            className={`font-bold shrink-0 mt-0.5 ${isPros ? 'text-emerald-600' : 'text-rose-600'}`}
          >
            {isPros ? <CheckCircle2 className="h-4 w-4" /> : <XCircle className="h-4 w-4" />}
          </span>
          <span className="flex flex-col gap-1 min-w-0">
            <span className="font-bold text-slate-900">{item.point}</span>
            {item.evidence && (
              <span
                className={`text-[11px] leading-snug italic font-medium ${
                  isPros ? 'text-emerald-800' : 'text-rose-800'
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
          <div className="inline-flex items-center gap-1.5 rounded-full border border-emerald-200 bg-emerald-50 px-3.5 py-1.5 text-xs font-bold text-emerald-700">
            <ThumbsUp className="h-4 w-4" />
            <span className="capitalize">Positive Sentiment</span>
          </div>
        );
      case 'negative':
        return (
          <div className="inline-flex items-center gap-1.5 rounded-full border border-rose-200 bg-rose-50 px-3.5 py-1.5 text-xs font-bold text-rose-700">
            <ThumbsDown className="h-4 w-4" />
            <span className="capitalize">Negative Sentiment</span>
          </div>
        );
      case 'mixed':
        return (
          <div className="inline-flex items-center gap-1.5 rounded-full border border-purple-200 bg-purple-50 px-3.5 py-1.5 text-xs font-bold text-purple-700">
            <Scale className="h-4 w-4" />
            <span className="capitalize">Mixed Sentiment</span>
          </div>
        );
      case 'neutral':
      default:
        return (
          <div className="inline-flex items-center gap-1.5 rounded-full border border-amber-200 bg-amber-50 px-3.5 py-1.5 text-xs font-bold text-amber-700">
            <Scale className="h-4 w-4" />
            <span className="capitalize">Neutral Sentiment</span>
          </div>
        );
    }
  };

  return (
    <div className="space-y-6 animate-fadeIn">
      {/* 1. Executive Summary & Verdict Header */}
      <div className="modern-card p-6 space-y-5">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-100 pb-4">
          <div className="flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-indigo-600" />
            <h3 className="text-base font-bold text-slate-900">AI Review Intelligence Summary</h3>
          </div>
          <div className="flex items-center gap-3">
            {renderSentimentBadge()}
            {analysis.rating != null && (
              <div className="inline-flex items-center gap-1 rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-xs font-bold text-amber-800">
                <Star className="h-3.5 w-3.5 fill-amber-500 text-amber-500" />
                <span>{analysis.rating} / 5</span>
              </div>
            )}
          </div>
        </div>

        {/* Summary Text */}
        <div className="rounded-2xl border border-indigo-100 bg-indigo-50/40 p-4">
          <p className="text-xs sm:text-sm text-slate-800 leading-relaxed font-medium">
            {analysis.summary}
          </p>
        </div>

        {/* Aspects Breakdown */}
        {analysis.aspects && analysis.aspects.length > 0 && (
          <div className="space-y-2 pt-2">
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500 block">
              Aspect Sentiment Breakdown:
            </span>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2.5">
              {analysis.aspects.map((asp, i) => {
                const isPos = asp.sentiment === 'positive';
                const isNeg = asp.sentiment === 'negative';
                return (
                  <div
                    key={i}
                    className="p-3 rounded-xl border border-slate-200 bg-white space-y-1 shadow-2xs"
                  >
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-bold text-slate-900">{asp.aspect}</span>
                      <span
                        className={`text-[10px] font-bold uppercase px-2 py-0.5 rounded-full ${
                          isPos
                            ? 'bg-emerald-50 text-emerald-700'
                            : isNeg
                            ? 'bg-rose-50 text-rose-700'
                            : 'bg-amber-50 text-amber-700'
                        }`}
                      >
                        {asp.sentiment}
                      </span>
                    </div>
                    {asp.evidence && (
                      <p className="text-[11px] text-slate-500 italic line-clamp-2">
                        “{asp.evidence}”
                      </p>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>

      {/* 2. Pros & Cons Split */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Pros */}
        <div className="modern-card p-6 space-y-4">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3">
            <h4 className="text-sm font-bold text-emerald-800 flex items-center gap-2">
              <ThumbsUp className="h-4 w-4 text-emerald-600" />
              <span>Key Strengths & Pros</span>
            </h4>
            <span className="text-xs font-bold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full">
              {analysis.pros?.length || 0} Points
            </span>
          </div>
          {analysis.pros && analysis.pros.length > 0 ? (
            renderPointEvidenceList(analysis.pros, 'emerald')
          ) : (
            <p className="text-xs text-slate-400 italic">No explicit pros detected.</p>
          )}
        </div>

        {/* Cons */}
        <div className="modern-card p-6 space-y-4">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3">
            <h4 className="text-sm font-bold text-rose-800 flex items-center gap-2">
              <ThumbsDown className="h-4 w-4 text-rose-600" />
              <span>Complaints & Cons</span>
            </h4>
            <span className="text-xs font-bold text-rose-700 bg-rose-50 px-2 py-0.5 rounded-full">
              {analysis.cons?.length || 0} Points
            </span>
          </div>
          {analysis.cons && analysis.cons.length > 0 ? (
            renderPointEvidenceList(analysis.cons, 'rose')
          ) : (
            <p className="text-xs text-slate-400 italic">No significant complaints found.</p>
          )}
        </div>
      </div>

      {/* 3. JSON Output Inspector */}
      <div className="flex items-center justify-between pt-2">
        <button
          onClick={() => setShowJson(!showJson)}
          className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-500 hover:text-slate-800 transition"
        >
          <Code2 className="h-4 w-4" />
          <span>{showJson ? 'Hide Structured JSON' : 'View Structured JSON'}</span>
        </button>

        {showJson && (
          <button
            onClick={handleCopyJson}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-200 bg-white text-xs font-semibold text-slate-700 hover:bg-slate-50 transition shadow-2xs"
          >
            {copied ? <Check className="h-3.5 w-3.5 text-emerald-600" /> : <Copy className="h-3.5 w-3.5" />}
            <span>{copied ? 'Copied' : 'Copy JSON'}</span>
          </button>
        )}
      </div>

      {showJson && (
        <div className="modern-card p-4 overflow-x-auto">
          <pre className="text-xs font-mono text-slate-800 leading-relaxed">
            {JSON.stringify(analysis, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
};
