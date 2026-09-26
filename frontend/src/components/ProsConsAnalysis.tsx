import React, { useEffect, useState } from 'react';
import {
  CheckCircle2,
  XCircle,
  ExternalLink,
  ShieldCheck,
  Star,
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
      <div className="flex items-center gap-0.5 text-[#D4AF5A]">
        {[1, 2, 3, 4, 5].map((s) => (
          <Star
            key={s}
            className={`h-3 w-3 ${
              s <= clamped ? 'fill-[#D4AF5A] text-[#D4AF5A]' : 'text-[#292A2B]'
            }`}
          />
        ))}
      </div>
    );
  };

  if (loading) {
    return (
      <div className="premium-panel p-12 text-center space-y-3">
        <div className="inline-block h-6 w-6 animate-spin rounded-full border-2 border-[#D4AF5A] border-t-transparent" />
        <p className="text-xs text-[#AAA79F]">
          Analyzing product-level pros and cons from dataset reviews...
        </p>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="rounded-xl border border-rose-900/40 bg-rose-950/20 p-5 text-center text-xs text-rose-300">
        {error || 'Pros and Cons analysis currently unavailable.'}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Section Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-[#292A2B] pb-3">
        <div>
          <h2 className="text-lg font-medium text-[#F5F2EA] flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-[#D4AF5A]" />
            Pros & Cons Intelligence
          </h2>
          <p className="text-xs text-[#74736E]">
            Quantified from {data.total_analyzed_reviews.toLocaleString()} actual reviews for{' '}
            <strong className="text-[#AAA79F] font-medium">{productTitle}</strong>
          </p>
        </div>

        <span className="rounded-full border border-[#D4AF5A]/30 bg-[#1B1915] px-3 py-1 text-[10px] font-mono text-[#D4AF5A] flex items-center gap-1.5 self-start sm:self-center">
          <ShieldCheck className="h-3.5 w-3.5 text-[#D4AF5A]" />
          <span>Evidence-Backed & Traceable</span>
        </span>
      </div>

      {/* Grid: Common Pros vs Common Cons */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* COMMON PROS */}
        <div className="premium-panel p-6 space-y-4">
          <div className="flex items-center justify-between border-b border-[#292A2B] pb-3">
            <h3 className="text-sm font-medium text-emerald-400 flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4" />
              Common Pros
            </h3>
            <span className="text-xs text-[#74736E]">
              {data.pros.length} key strengths
            </span>
          </div>

          <div className="space-y-3">
            {data.pros.length === 0 ? (
              <p className="text-xs text-[#74736E] italic">No dominant pros identified in available dataset.</p>
            ) : (
              data.pros.map((pro, index) => (
                <div
                  key={index}
                  className="rounded-xl border border-[#292A2B] bg-[#151617] p-4 space-y-2.5 transition hover:border-emerald-500/40"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="space-y-0.5">
                      <h4 className="text-sm font-medium text-[#F5F2EA] flex items-center gap-2">
                        <span className="text-emerald-400 text-xs font-mono">{index + 1}.</span>
                        <span>{pro.theme}</span>
                      </h4>
                      <p className="text-[11px] text-[#AAA79F]">
                        Mentioned in: <strong className="text-emerald-400">{pro.review_count.toLocaleString()} reviews</strong> ({pro.percentage}% of reviews)
                      </p>
                    </div>

                    <button
                      onClick={() => handleOpenEvidence(pro, 'pro')}
                      className="inline-flex items-center gap-1 rounded-lg border border-[#292A2B] bg-[#111213] px-2.5 py-1 text-[11px] font-medium text-[#D4AF5A] hover:border-[#D4AF5A]/40 hover:bg-[#1C1D1F] transition shrink-0"
                      title="View supporting reviews from dataset"
                    >
                      <ExternalLink className="h-3 w-3" />
                      <span>View Reviews</span>
                    </button>
                  </div>

                  {/* Example actual reviews */}
                  {pro.example_reviews && pro.example_reviews.length > 0 && (
                    <div className="space-y-1.5 pt-2 border-t border-[#292A2B]">
                      <span className="text-[10px] uppercase tracking-wider text-[#74736E]">
                        Example Customer Feedback:
                      </span>
                      {pro.example_reviews.map((ex, i) => (
                        <p key={i} className="text-xs text-[#AAA79F] italic line-clamp-2">
                          "{ex}"
                        </p>
                      ))}
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        </div>

        {/* COMMON CONS */}
        <div className="premium-panel p-6 space-y-4">
          <div className="flex items-center justify-between border-b border-[#292A2B] pb-3">
            <h3 className="text-sm font-medium text-rose-400 flex items-center gap-2">
              <XCircle className="h-4 w-4" />
              Common Cons
            </h3>
            <span className="text-xs text-[#74736E]">
              {data.cons.length} key pain points
            </span>
          </div>

          <div className="space-y-3">
            {data.cons.length === 0 ? (
              <p className="text-xs text-[#74736E] italic">No dominant cons identified in available dataset.</p>
            ) : (
              data.cons.map((con, index) => (
                <div
                  key={index}
                  className="rounded-xl border border-[#292A2B] bg-[#151617] p-4 space-y-2.5 transition hover:border-rose-500/40"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="space-y-0.5">
                      <h4 className="text-sm font-medium text-[#F5F2EA] flex items-center gap-2">
                        <span className="text-rose-400 text-xs font-mono">{index + 1}.</span>
                        <span>{con.theme}</span>
                      </h4>
                      <p className="text-[11px] text-[#AAA79F]">
                        Mentioned in: <strong className="text-rose-400">{con.review_count.toLocaleString()} reviews</strong> ({con.percentage}% of reviews)
                      </p>
                    </div>

                    <button
                      onClick={() => handleOpenEvidence(con, 'con')}
                      className="inline-flex items-center gap-1 rounded-lg border border-[#292A2B] bg-[#111213] px-2.5 py-1 text-[11px] font-medium text-[#D4AF5A] hover:border-[#D4AF5A]/40 hover:bg-[#1C1D1F] transition shrink-0"
                      title="View supporting reviews from dataset"
                    >
                      <ExternalLink className="h-3 w-3" />
                      <span>View Reviews</span>
                    </button>
                  </div>

                  {/* Example actual reviews */}
                  {con.example_reviews && con.example_reviews.length > 0 && (
                    <div className="space-y-1.5 pt-2 border-t border-[#292A2B]">
                      <span className="text-[10px] uppercase tracking-wider text-[#74736E]">
                        Example Customer Feedback:
                      </span>
                      {con.example_reviews.map((ex, i) => (
                        <p key={i} className="text-xs text-[#AAA79F] italic line-clamp-2">
                          "{ex}"
                        </p>
                      ))}
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      {/* Authenticity & Source Note */}
      {data.authenticity_signals && data.authenticity_signals.length > 0 && (
        <div className="rounded-xl border border-[#292A2B] bg-[#151617] p-4 flex flex-wrap items-center justify-between gap-4 text-xs text-[#AAA79F]">
          <div className="flex items-center gap-2">
            <span className="text-[#D4AF5A] font-semibold">Signals:</span>
            <span>{data.authenticity_signals.join(' · ')}</span>
          </div>
          <span className="text-[10px] text-[#74736E]">{data.source_label}</span>
        </div>
      )}

      {/* Evidence Modal Inspector */}
      {activeThemeModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
          <div className="relative max-h-[85vh] w-full max-w-2xl overflow-hidden rounded-2xl border border-[#292A2B] bg-[#111213] shadow-2xl flex flex-col">
            {/* Modal Header */}
            <div className="flex items-center justify-between border-b border-[#292A2B] p-5">
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <span
                    className={`text-xs uppercase tracking-wider font-semibold ${
                      activeThemeModal.type === 'pro' ? 'text-emerald-400' : 'text-rose-400'
                    }`}
                  >
                    {activeThemeModal.type === 'pro' ? 'Pro Evidence' : 'Con Evidence'}
                  </span>
                  <span className="text-[#74736E]">·</span>
                  <span className="text-xs text-[#74736E]">
                    {activeThemeModal.theme.review_count.toLocaleString()} verified mentions
                  </span>
                </div>
                <h3 className="text-lg font-medium text-[#F5F2EA]">
                  {activeThemeModal.theme.theme}
                </h3>
              </div>

              <button
                onClick={() => setActiveThemeModal(null)}
                className="rounded-lg p-2 text-[#74736E] hover:bg-[#1C1D1F] hover:text-[#F5F2EA] transition"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            {/* Modal Body */}
            <div className="flex-1 overflow-y-auto p-5 space-y-4">
              {loadingEvidence ? (
                <div className="flex flex-col items-center justify-center py-12 space-y-3">
                  <div className="h-6 w-6 animate-spin rounded-full border-2 border-[#D4AF5A] border-t-transparent" />
                  <p className="text-xs text-[#AAA79F]">Retrieving actual dataset reviews...</p>
                </div>
              ) : evidenceReviews.length === 0 ? (
                <div className="py-12 text-center text-xs text-[#74736E]">
                  No direct review snippets found for this theme.
                </div>
              ) : (
                evidenceReviews.map((rev) => (
                  <article
                    key={rev.id}
                    className="rounded-xl border border-[#292A2B] bg-[#151617] p-4 space-y-2 text-xs"
                  >
                    <div className="flex items-center justify-between gap-2">
                      {renderStars(rev.rating)}
                      <span className="text-[10px] text-[#74736E] uppercase font-mono">
                        Review #{rev.id} · {rev.sentiment}
                      </span>
                    </div>
                    <p className="text-xs leading-relaxed text-[#F5F2EA]">
                      "{rev.review_text}"
                    </p>
                  </article>
                ))
              )}
            </div>

            {/* Modal Footer */}
            <div className="border-t border-[#292A2B] bg-[#151617] px-5 py-3 text-right">
              <button
                onClick={() => setActiveThemeModal(null)}
                className="rounded-lg border border-[#292A2B] bg-[#111213] px-4 py-1.5 text-xs text-[#F5F2EA] hover:bg-[#1C1D1F] transition"
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
