import React, { useEffect, useState } from 'react';
import {
  CheckCircle2,
  XCircle,
  FileText,
  ExternalLink,
  ShieldCheck,
  Star,
  Database,
  X,
  Sparkles,
} from 'lucide-react';
import {
  ProsConsAnalysisResponse,
  ProConTheme,
  ReviewItem,
} from '../types/ecommerce';
import { getProductProsCons, getThemeSupportingReviews } from '../services/api';

interface ProsConsAnalysisProps {
  productId: string;
  productTitle: string;
}

export const ProsConsAnalysis: React.FC<ProsConsAnalysisProps> = ({
  productId,
  productTitle,
}) => {
  const [data, setData] = useState<ProsConsAnalysisResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string>('');

  // Evidence modal state
  const [activeThemeModal, setActiveThemeModal] = useState<{
    theme: ProConTheme;
    type: 'pro' | 'con';
  } | null>(null);
  const [evidenceReviews, setEvidenceReviews] = useState<ReviewItem[]>([]);
  const [loadingEvidence, setLoadingEvidence] = useState<boolean>(false);

  useEffect(() => {
    let isMounted = true;
    setLoading(true);
    setError('');

    getProductProsCons(productId)
      .then((res) => {
        if (isMounted) {
          setData(res);
          setError('');
        }
      })
      .catch((err) => {
        if (isMounted) {
          setError(
            err.response?.data?.detail || 'Failed to load Pros & Cons analysis.'
          );
        }
      })
      .finally(() => {
        if (isMounted) setLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [productId]);

  const handleOpenEvidence = async (theme: ProConTheme, type: 'pro' | 'con') => {
    setActiveThemeModal({ theme, type });
    setLoadingEvidence(true);
    try {
      const reviews = await getThemeSupportingReviews(
        productId,
        theme.theme,
        type === 'pro' ? 'positive' : 'negative',
        30
      );
      setEvidenceReviews(reviews);
    } catch {
      setEvidenceReviews([]);
    } finally {
      setLoadingEvidence(false);
    }
  };

  const renderStars = (rating: number) => {
    const clamped = Math.max(1, Math.min(5, Math.round(rating)));
    return (
      <div className="flex items-center gap-0.5 text-amber-400">
        {[1, 2, 3, 4, 5].map((s) => (
          <Star
            key={s}
            className={`h-3.5 w-3.5 ${
              s <= clamped ? 'fill-amber-400 text-amber-400' : 'text-slate-600'
            }`}
          />
        ))}
      </div>
    );
  };

  if (loading) {
    return (
      <div className="rounded-2xl border border-white/10 bg-[#111827]/80 p-12 text-center space-y-3">
        <div className="inline-block h-7 w-7 animate-spin rounded-full border-2 border-purple-400 border-t-transparent" />
        <p className="text-xs text-slate-400 font-mono">
          Analyzing product-level pros and cons from dataset reviews...
        </p>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 p-5 text-center text-xs text-rose-300">
        {error || 'Pros and Cons analysis currently unavailable.'}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Section Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-800 pb-3">
        <div>
          <h2 className="text-lg font-bold text-white flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-purple-400" />
            Pros & Cons Analysis
          </h2>
          <p className="text-xs text-slate-400">
            Quantified from {data.total_analyzed_reviews.toLocaleString()} actual reviews for{' '}
            <strong className="text-slate-200">{productTitle}</strong>
          </p>
        </div>

        <span className="rounded-full bg-cyan-500/10 border border-cyan-500/30 px-2.5 py-1 text-[11px] font-mono text-cyan-300 flex items-center gap-1.5 self-start sm:self-center">
          <ShieldCheck className="h-3.5 w-3.5 text-cyan-400" />
          <span>Evidence-Backed & Traceable</span>
        </span>
      </div>

      {/* Grid: Common Pros (Left) vs Common Cons (Right) */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* COMMON PROS */}
        <div className="rounded-2xl border border-emerald-500/30 bg-[#111827]/90 p-6 backdrop-blur-xl shadow-glass space-y-4">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <h3 className="text-sm font-bold text-emerald-400 flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4" />
              COMMON PROS
            </h3>
            <span className="text-[11px] font-mono text-slate-400">
              {data.pros.length} key strengths
            </span>
          </div>

          <div className="space-y-4">
            {data.pros.map((pro, index) => (
              <div
                key={index}
                className="rounded-xl border border-emerald-500/20 bg-emerald-950/20 p-4 space-y-2.5 transition hover:border-emerald-500/40"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="space-y-0.5">
                    <h4 className="text-sm font-bold text-white flex items-center gap-2">
                      <span className="text-emerald-400 font-mono text-xs">{index + 1}.</span>
                      <span>{pro.theme}</span>
                    </h4>
                    <p className="text-[11px] font-mono text-emerald-300">
                      Mentioned in: <strong>{pro.review_count.toLocaleString()} reviews</strong> ({pro.percentage}% of analyzed reviews)
                    </p>
                  </div>

                  <button
                    onClick={() => handleOpenEvidence(pro, 'pro')}
                    className="inline-flex items-center gap-1 rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-2.5 py-1 text-[11px] font-semibold text-emerald-300 hover:bg-emerald-500/20 transition shrink-0"
                    title="View supporting reviews from dataset"
                  >
                    <ExternalLink className="h-3 w-3" />
                    <span>View Reviews</span>
                  </button>
                </div>

                {/* Example actual reviews */}
                {pro.example_reviews && pro.example_reviews.length > 0 && (
                  <div className="space-y-1.5 pt-1 border-t border-emerald-500/10">
                    <span className="text-[10px] uppercase font-mono tracking-wider text-slate-500">
                      Example Customer Feedback:
                    </span>
                    {pro.example_reviews.map((ex, i) => (
                      <p key={i} className="text-xs text-slate-300 italic line-clamp-2">
                        "{ex}"
                      </p>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* COMMON CONS */}
        <div className="rounded-2xl border border-rose-500/30 bg-[#111827]/90 p-6 backdrop-blur-xl shadow-glass space-y-4">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <h3 className="text-sm font-bold text-rose-400 flex items-center gap-2">
              <XCircle className="h-4 w-4" />
              COMMON CONS
            </h3>
            <span className="text-[11px] font-mono text-slate-400">
              {data.cons.length} key pain points
            </span>
          </div>

          <div className="space-y-4">
            {data.cons.map((con, index) => (
              <div
                key={index}
                className="rounded-xl border border-rose-500/20 bg-rose-950/20 p-4 space-y-2.5 transition hover:border-rose-500/40"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="space-y-0.5">
                    <h4 className="text-sm font-bold text-white flex items-center gap-2">
                      <span className="text-rose-400 font-mono text-xs">{index + 1}.</span>
                      <span>{con.theme}</span>
                    </h4>
                    <p className="text-[11px] font-mono text-rose-300">
                      Mentioned in: <strong>{con.review_count.toLocaleString()} reviews</strong> ({con.percentage}% of analyzed reviews)
                    </p>
                  </div>

                  <button
                    onClick={() => handleOpenEvidence(con, 'con')}
                    className="inline-flex items-center gap-1 rounded-lg border border-rose-500/30 bg-rose-500/10 px-2.5 py-1 text-[11px] font-semibold text-rose-300 hover:bg-rose-500/20 transition shrink-0"
                    title="View supporting reviews from dataset"
                  >
                    <ExternalLink className="h-3 w-3" />
                    <span>View Reviews</span>
                  </button>
                </div>

                {/* Example actual reviews */}
                {con.example_reviews && con.example_reviews.length > 0 && (
                  <div className="space-y-1.5 pt-1 border-t border-rose-500/10">
                    <span className="text-[10px] uppercase font-mono tracking-wider text-slate-500">
                      Example Customer Feedback:
                    </span>
                    {con.example_reviews.map((ex, i) => (
                      <p key={i} className="text-xs text-slate-300 italic line-clamp-2">
                        "{ex}"
                      </p>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* PRODUCT REVIEW SUMMARY (Detailed Synthesis Card) */}
      <div className="relative overflow-hidden rounded-2xl border border-white/10 bg-[#111827]/85 p-6 backdrop-blur-xl shadow-glass space-y-5">
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <h3 className="text-sm font-bold text-white flex items-center gap-2">
            <FileText className="h-4 w-4 text-purple-400" />
            PRODUCT REVIEW SUMMARY
          </h3>
          <span className="text-xs font-mono text-slate-400">
            {productTitle}
          </span>
        </div>

        {/* Overall Synthesis */}
        <div className="rounded-xl border border-slate-800 bg-[#0B0F17]/80 p-4 text-sm text-slate-200 leading-relaxed">
          <strong className="text-purple-300 block mb-1">Overall Assessment:</strong>
          {data.summary}
        </div>

        {/* Highlights: What Customers Commonly Liked / Disliked */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
          <div className="rounded-xl border border-emerald-500/20 bg-emerald-950/15 p-4 space-y-2">
            <span className="font-bold text-emerald-400 block">
              What customers commonly liked:
            </span>
            <div className="flex flex-wrap gap-1.5">
              {data.top_pros.map((p, i) => (
                <span
                  key={i}
                  className="rounded-lg bg-emerald-500/20 border border-emerald-500/30 px-2 py-0.5 text-emerald-200 font-medium"
                >
                  ✓ {p}
                </span>
              ))}
            </div>
          </div>

          <div className="rounded-xl border border-rose-500/20 bg-rose-950/15 p-4 space-y-2">
            <span className="font-bold text-rose-400 block">
              What customers commonly disliked:
            </span>
            <div className="flex flex-wrap gap-1.5">
              {data.top_cons.map((c, i) => (
                <span
                  key={i}
                  className="rounded-lg bg-rose-500/20 border border-rose-500/30 px-2 py-0.5 text-rose-200 font-medium"
                >
                  ✗ {c}
                </span>
              ))}
            </div>
          </div>
        </div>

        {/* Bottom Metrics Bar */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-2 text-xs font-mono">
          <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-3">
            <span className="text-slate-500 block text-[10px]">REVIEW VOLUME</span>
            <span className="text-base font-bold text-white">
              {data.review_volume.toLocaleString()} reviews
            </span>
          </div>

          <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-3">
            <span className="text-slate-500 block text-[10px]">AVERAGE RATING</span>
            <span className="text-base font-bold text-amber-400">
              {data.average_rating} / 5.0 ★
            </span>
          </div>

          <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-3 sm:col-span-2">
            <span className="text-slate-500 block text-[10px]">SENTIMENT BREAKDOWN</span>
            <div className="flex items-center gap-3 mt-1 text-xs">
              <span className="text-emerald-400">
                Positive {data.sentiment_percentages['positive']}%
              </span>
              <span className="text-slate-600">•</span>
              <span className="text-amber-400">
                Neutral {data.sentiment_percentages['neutral']}%
              </span>
              <span className="text-slate-600">•</span>
              <span className="text-rose-400">
                Negative {data.sentiment_percentages['negative']}%
              </span>
            </div>
          </div>
        </div>

        {/* Authenticity Signals */}
        {data.authenticity_signals && data.authenticity_signals.length > 0 && (
          <div className="rounded-xl border border-cyan-500/20 bg-cyan-950/15 p-4 space-y-2">
            <div className="flex items-center gap-1.5 text-xs font-bold text-cyan-300">
              <ShieldCheck className="h-4 w-4 text-cyan-400" />
              <span>Review Authenticity Signals</span>
            </div>
            <ul className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs text-slate-300">
              {data.authenticity_signals.map((sig, idx) => (
                <li key={idx} className="flex items-start gap-1.5">
                  <span className="text-cyan-400 font-bold">•</span>
                  <span>{sig}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {/* SUPPORTING REVIEWS EVIDENCE MODAL */}
      {activeThemeModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4 backdrop-blur-sm animate-fadeIn">
          <div className="relative w-full max-w-2xl max-h-[85vh] overflow-y-auto rounded-2xl border border-purple-500/30 bg-[#0B0F17] p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div>
                <div className="flex items-center gap-2">
                  {activeThemeModal.type === 'pro' ? (
                    <CheckCircle2 className="h-5 w-5 text-emerald-400" />
                  ) : (
                    <XCircle className="h-5 w-5 text-rose-400" />
                  )}
                  <h3 className="text-base font-bold text-white">
                    Supporting Reviews for: {activeThemeModal.theme.theme}
                  </h3>
                </div>
                <p className="text-xs font-mono text-slate-400 mt-0.5">
                  Detected in {activeThemeModal.theme.review_count.toLocaleString()} reviews ({activeThemeModal.theme.percentage}% of analyzed reviews)
                </p>
              </div>

              <button
                onClick={() => setActiveThemeModal(null)}
                className="rounded-lg p-1 text-slate-400 hover:bg-slate-800 hover:text-white transition"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            {loadingEvidence ? (
              <div className="py-12 text-center space-y-2">
                <div className="inline-block h-6 w-6 animate-spin rounded-full border-2 border-purple-400 border-t-transparent" />
                <p className="text-xs text-slate-400 font-mono">
                  Retrieving supporting reviews from dataset...
                </p>
              </div>
            ) : evidenceReviews.length === 0 ? (
              <div className="py-8 text-center text-xs text-slate-400">
                No matching review excerpts found.
              </div>
            ) : (
              <div className="space-y-3">
                <div className="text-[11px] font-mono text-cyan-300 flex items-center gap-1">
                  <Database className="h-3 w-3" />
                  <span>Showing real review excerpts from dataset for {productTitle}:</span>
                </div>

                <div className="space-y-2.5 max-h-[50vh] overflow-y-auto pr-1">
                  {evidenceReviews.map((rev) => (
                    <div
                      key={rev.id}
                      className="rounded-xl border border-slate-800 bg-[#111827]/70 p-3.5 space-y-2 text-xs hover:border-slate-700 transition"
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          {renderStars(rev.rating)}
                          <span className="font-mono text-slate-400 font-semibold">
                            {rev.rating}/5
                          </span>
                        </div>
                        <span className="font-mono text-[10px] text-slate-500">
                          Review #{rev.id}
                        </span>
                      </div>

                      <p className="text-slate-200 leading-relaxed italic">
                        "{rev.review_text}"
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div className="flex justify-between items-center pt-2 border-t border-slate-800">
              <span className="text-[11px] font-mono text-slate-500">
                Source: ReviewIQ Product Review Dataset
              </span>
              <button
                onClick={() => setActiveThemeModal(null)}
                className="rounded-xl bg-slate-800 px-4 py-2 text-xs font-semibold text-slate-200 hover:bg-slate-700"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
