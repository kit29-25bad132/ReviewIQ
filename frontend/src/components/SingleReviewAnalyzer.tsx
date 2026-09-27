import React, { useState } from 'react';
import {
  Sparkles,
  Star,
  ThumbsUp,
  ThumbsDown,
  Layers,
  Loader2,
  AlertCircle,
  Copy,
  Check,
} from 'lucide-react';
import { analyzeReview } from '../services/api';
import { ReviewAnalysis } from '../types/review';

const SAMPLE_REVIEWS = [
  {
    title: 'Positive: Noise Cancelling Headphones',
    text: 'These headphones have phenomenal sound quality and the active noise cancellation completely blocks airplane drone. The battery lasted an entire 26-hour international trip. My only slight complaint is the headband gets a little warm after 4 hours.',
  },
  {
    title: 'Mixed: Smart Watch Review',
    text: 'The AMOLED screen is stunning and heart rate tracking is accurate during workouts. However, the battery life is disappointing as it requires daily charging. The companion mobile app also randomly crashes during sync.',
  },
  {
    title: 'Negative: Coffee Maker Complaint',
    text: 'Extremely frustrated with this purchase. The machine leaked water all over my counter after 2 weeks of use. Customer support was unhelpful and refused a replacement. The coffee also brewed lukewarm at best.',
  },
];

export const SingleReviewAnalyzer: React.FC = () => {
  const [reviewText, setReviewText] = useState('');
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analysis, setAnalysis] = useState<ReviewAnalysis | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const handleAnalyze = async (textToAnalyze?: string) => {
    const text = (textToAnalyze !== undefined ? textToAnalyze : reviewText).trim();
    if (!text) return;

    setIsAnalyzing(true);
    setError(null);

    try {
      const result = await analyzeReview(text);
      setAnalysis(result);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'AI review analysis failed. Check backend connection.'
      );
    } finally {
      setIsAnalyzing(false);
    }
  };

  const handleSampleClick = (sampleText: string) => {
    setReviewText(sampleText);
    handleAnalyze(sampleText);
  };

  const handleCopyAnalysis = () => {
    if (!analysis) return;
    navigator.clipboard.writeText(JSON.stringify(analysis, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="mx-auto max-w-5xl px-4 py-8 sm:px-6 lg:px-8">
      {/* Header */}
      <div className="mb-8 text-center sm:text-left">
        <div className="mb-2 flex items-center justify-center sm:justify-start gap-2">
          <span className="h-1.5 w-1.5 rounded-full bg-[#D4AF5A]" />
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-[#D4AF5A]">
            LangGraph AI Pipeline
          </p>
        </div>
        <h2 className="text-2xl sm:text-3xl font-semibold tracking-tight text-[#F5F2EA]">
          Ad-Hoc Review Intelligence Analyzer
        </h2>
        <p className="mt-2 text-sm text-[#AAA79F] max-w-2xl">
          Paste any arbitrary customer review text to test ReviewIQ's real-time aspect mining,
          sentiment breakdown, and evidence tracing engine.
        </p>
      </div>

      {/* Input Panel */}
      <div className="premium-panel p-6 border border-[#292A2B] bg-[#141517]">
        <label className="block text-xs font-semibold uppercase tracking-wider text-[#AAA79F] mb-2">
          Customer Review Text
        </label>
        <textarea
          rows={5}
          value={reviewText}
          onChange={(e) => setReviewText(e.target.value)}
          placeholder="Paste or type a customer review here (e.g. 'The battery life is amazing, lasting over 2 days, but the bluetooth connection drops frequently...')..."
          className="w-full rounded-xl border border-[#292A2B] bg-[#18191B] p-4 text-sm text-[#F5F2EA] placeholder:text-[#74736E] focus:outline-none focus:border-[#D4AF5A]/60 transition"
        />

        {/* Action bar and sample buttons */}
        <div className="mt-4 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-1.5 text-xs text-[#74736E]">
            <span className="font-medium mr-1">Load sample:</span>
            {SAMPLE_REVIEWS.map((sample, idx) => (
              <button
                key={idx}
                type="button"
                onClick={() => handleSampleClick(sample.text)}
                className="rounded-md border border-[#292A2B] bg-[#18191B] px-2.5 py-1 text-[11px] text-[#AAA79F] hover:border-[#D4AF5A]/40 hover:text-[#F0D58A] transition"
              >
                {sample.title.split(':')[0]}
              </button>
            ))}
          </div>

          <button
            onClick={() => handleAnalyze()}
            disabled={isAnalyzing || !reviewText.trim()}
            className="gold-button flex w-full sm:w-auto items-center justify-center gap-2 px-6 py-2.5 text-xs font-semibold disabled:opacity-50 disabled:cursor-not-allowed shrink-0"
          >
            {isAnalyzing ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Analyzing with AI...
              </>
            ) : (
              <>
                <Sparkles className="h-4 w-4" />
                Analyze Review
              </>
            )}
          </button>
        </div>
      </div>

      {/* Error state */}
      {error && (
        <div className="mt-6 rounded-xl border border-rose-900/40 bg-rose-950/20 p-4 text-xs text-rose-300 flex items-start gap-3">
          <AlertCircle className="h-4 w-4 text-rose-400 shrink-0 mt-0.5" />
          <div>
            <p className="font-semibold text-rose-200">Analysis Error</p>
            <p className="mt-1 leading-relaxed">{error}</p>
          </div>
        </div>
      )}

      {/* Results View */}
      {analysis && (
        <div className="mt-8 space-y-6">
          {/* Summary and Overview */}
          <div className="premium-panel p-6 border border-[#292A2B] bg-[#141517]">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4 pb-4 border-b border-[#242526]">
              <div className="flex items-center gap-3">
                <span
                  className={`rounded-full px-3 py-1 text-xs font-bold uppercase tracking-wider ${
                    analysis.sentiment === 'positive'
                      ? 'bg-emerald-950/70 text-emerald-400 border border-emerald-500/30'
                      : analysis.sentiment === 'negative'
                      ? 'bg-rose-950/70 text-rose-400 border border-rose-500/30'
                      : 'bg-amber-950/70 text-amber-400 border border-amber-500/30'
                  }`}
                >
                  {analysis.sentiment} sentiment
                </span>

                {analysis.rating !== null && (
                  <div className="flex items-center gap-1.5 text-xs text-[#F5F2EA] font-semibold bg-[#1C1D1F] px-2.5 py-1 rounded-md border border-[#292A2B]">
                    <Star className="h-3.5 w-3.5 fill-[#D4AF5A] text-[#D4AF5A]" />
                    <span>{analysis.rating} / 5</span>
                    <span className="text-[10px] text-[#74736E] font-normal">
                      ({analysis.rating_source})
                    </span>
                  </div>
                )}
              </div>

              <button
                onClick={handleCopyAnalysis}
                className="flex items-center gap-1.5 text-xs text-[#AAA79F] hover:text-[#F5F2EA] transition"
              >
                {copied ? <Check className="h-3.5 w-3.5 text-emerald-400" /> : <Copy className="h-3.5 w-3.5" />}
                {copied ? 'Copied JSON' : 'Export Analysis'}
              </button>
            </div>

            <div>
              <p className="text-xs uppercase tracking-wider text-[#74736E] font-medium mb-1">
                Executive Synthesis
              </p>
              <p className="text-sm sm:text-base leading-relaxed text-[#F5F2EA]">
                {analysis.summary}
              </p>
            </div>
          </div>

          {/* Dynamic Aspects from this Review */}
          {analysis.aspects && analysis.aspects.length > 0 && (
            <div className="premium-panel p-6 border border-[#292A2B] bg-[#141517]">
              <div className="flex items-center gap-2 mb-4">
                <Layers className="h-4 w-4 text-[#D4AF5A]" />
                <h3 className="text-sm font-semibold text-[#F5F2EA] uppercase tracking-wide">
                  Aspect Sentiment & Evidence
                </h3>
              </div>

              <div className="grid gap-3 sm:grid-cols-2">
                {analysis.aspects.map((asp, i) => (
                  <div
                    key={i}
                    className="rounded-xl border border-[#292A2B] bg-[#18191B] p-4 flex flex-col justify-between"
                  >
                    <div>
                      <div className="flex items-center justify-between gap-2 mb-2">
                        <span className="text-sm font-semibold text-[#F5F2EA]">
                          {asp.aspect}
                        </span>
                        <span
                          className={`rounded px-2 py-0.5 text-[10px] font-semibold uppercase ${
                            asp.sentiment === 'positive'
                              ? 'bg-emerald-950/60 text-emerald-400 border border-emerald-500/20'
                              : asp.sentiment === 'negative'
                              ? 'bg-rose-950/60 text-rose-400 border border-rose-500/20'
                              : 'bg-amber-950/60 text-amber-400 border border-amber-500/20'
                          }`}
                        >
                          {asp.sentiment}
                        </span>
                      </div>
                      <p className="text-xs text-[#AAA79F] leading-relaxed italic border-l-2 border-[#D4AF5A]/40 pl-3 mt-2">
                        "{asp.evidence}"
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Pros & Cons Columns */}
          <div className="grid gap-6 sm:grid-cols-2">
            {/* Pros */}
            <div className="premium-panel p-6 border border-[#292A2B] bg-[#141517]">
              <div className="flex items-center gap-2 mb-4 text-emerald-400">
                <ThumbsUp className="h-4 w-4" />
                <h3 className="text-sm font-semibold uppercase tracking-wide">
                  Identified Pros ({analysis.pros?.length || 0})
                </h3>
              </div>

              {analysis.pros?.length === 0 ? (
                <p className="text-xs text-[#74736E] italic">No positive claims detected.</p>
              ) : (
                <div className="space-y-3">
                  {analysis.pros.map((p, idx) => (
                    <div key={idx} className="rounded-lg border border-[#292A2B] bg-[#18191B] p-3.5">
                      <p className="text-xs font-semibold text-[#F5F2EA]">{p.point}</p>
                      {p.evidence && (
                        <p className="text-[11px] text-[#AAA79F] italic mt-1 pl-3 border-l border-emerald-500/30">
                          "{p.evidence}"
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Cons */}
            <div className="premium-panel p-6 border border-[#292A2B] bg-[#141517]">
              <div className="flex items-center gap-2 mb-4 text-rose-400">
                <ThumbsDown className="h-4 w-4" />
                <h3 className="text-sm font-semibold uppercase tracking-wide">
                  Identified Cons ({analysis.cons?.length || 0})
                </h3>
              </div>

              {analysis.cons?.length === 0 ? (
                <p className="text-xs text-[#74736E] italic">No negative claims detected.</p>
              ) : (
                <div className="space-y-3">
                  {analysis.cons.map((c, idx) => (
                    <div key={idx} className="rounded-lg border border-[#292A2B] bg-[#18191B] p-3.5">
                      <p className="text-xs font-semibold text-[#F5F2EA]">{c.point}</p>
                      {c.evidence && (
                        <p className="text-[11px] text-[#AAA79F] italic mt-1 pl-3 border-l border-rose-500/30">
                          "{c.evidence}"
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
