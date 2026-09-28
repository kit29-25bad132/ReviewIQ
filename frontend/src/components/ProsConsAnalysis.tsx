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
      <div className="flex items-center gap-0.5 text-amber-400">
        {[1, 2, 3, 4, 5].map((s) => (
          <Star
            key={s}
            className={`h-3 w-3 ${
              s <= clamped ? 'fill-amber-400 text-amber-400' : 'text-slate-200'
            }`}
          />
        ))}
      </div>
    );
  };

  if (loading) {
    return (
      <div className="modern-card p-12 text-center space-y-3">
        <div className="inline-block h-6 w-6 animate-spin rounded-full border-2 border-indigo-600 border-t-transparent" />
        <p className="text-xs text-slate-500 font-medium">
          Analyzing product-level pros and cons from dataset reviews...
        </p>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="rounded-xl border border-rose-200 bg-rose-50 p-5 text-center text-xs text-rose-700">
        {error || 'Pros and Cons analysis currently unavailable.'}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Section Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-100 pb-3">
        <div>
          <h2 className="text-lg font-bold text-slate-900 flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-indigo-600" />
            Top Pros & Cons Intelligence
          </h2>
          <p className="text-xs text-slate-500">
            Quantified from {data.total_analyzed_reviews.toLocaleString()} actual customer reviews for{' '}
            <strong className="text-slate-700 font-semibold">{productTitle}</strong>
          </p>
        </div>

        <span className="rounded-full bg-emerald-50 border border-emerald-100 px-3 py-1 text-[11px] font-semibold text-emerald-700 flex items-center gap-1.5 self-start sm:self-center">
          <ShieldCheck className="h-3.5 w-3.5 text-emerald-600" />
          <span>Evidence-Backed & Traceable</span>
        </span>
      </div>

      {/* Grid: Common Pros vs Common Cons */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* COMMON PROS */}
        <div className="modern-card p-6 space-y-4 border-emerald-100 bg-gradient-to-b from-emerald-50/20 to-white">
          <div className="flex items-center justify-between border-b border-emerald-100 pb-3">
            <h3 className="text-sm font-bold text-emerald-800 flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 text-emerald-600" />
              Common Pros
            </h3>
            <span className="text-xs font-semibold text-emerald-700 bg-emerald-100/70 px-2 py-0.5 rounded-full">
              {data.pros.length} key strengths
            </span>
          </div>

          <div className="space-y-3">
            {data.pros.length === 0 ? (
              <p className="text-xs text-slate-400 italic">No dominant pros identified in available dataset.</p>
            ) : (
              data.pros.map((pro, index) => (
                <div
                  key={index}
                  className="rounded-xl border border-emerald-100 bg-white p-4 space-y-2.5 shadow-xs transition hover:border-emerald-300"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="space-y-0.5">
                      <h4 className="text-sm font-bold text-slate-800 flex items-center gap-2">
                        <span className="text-emerald-600 text-xs font-mono font-bold">{index + 1}.</span>
                        <span>{pro.theme}</span>
                      </h4>
                      <p className="text-[11px] text-slate-500">
                        Mentioned in: <strong className="text-emerald-700 font-bold">{pro.review_count.toLocaleString()} reviews</strong> ({pro.percentage}% of reviews)
                      </p>
                    </div>

                    <button
                      onClick={() => handleOpenEvidence(pro, 'pro')}
                      className="inline-flex items-center gap-1 rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-1 text-[11px] font-semibold text-indigo-600 hover:bg-indigo-50 hover:border-indigo-200 transition shrink-0"
                      title="View supporting reviews from dataset"
                    >
                      <ExternalLink className="h-3 w-3" />
                      <span>Evidence</span>
                    </button>
                  </div>

                  {/* Example actual reviews */}
                  {pro.example_reviews && pro.example_reviews.length > 0 && (
                    <div className="space-y-1.5 pt-2 border-t border-slate-100">
                      <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">
                        Customer Quote:
                      </span>
                      {pro.example_reviews.map((ex, i) => (
                        <p key={i} className="text-xs text-slate-600 italic line-clamp-2">
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
        <div className="modern-card p-6 space-y-4 border-rose-100 bg-gradient-to-b from-rose-50/20 to-white">
          <div className="flex items-center justify-between border-b border-rose-100 pb-3">
            <h3 className="text-sm font-bold text-rose-800 flex items-center gap-2">
              <XCircle className="h-4 w-4 text-rose-600" />
              Common Cons
            </h3>
            <span className="text-xs font-semibold text-rose-700 bg-rose-100/70 px-2 py-0.5 rounded-full">
              {data.cons.length} pain points
            </span>
          </div>

          <div className="space-y-3">
            {data.cons.length === 0 ? (
              <p className="text-xs text-slate-400 italic">No dominant cons identified in available dataset.</p>
            ) : (
              data.cons.map((con, index) => (
                <div
                  key={index}
                  className="rounded-xl border border-rose-100 bg-white p-4 space-y-2.5 shadow-xs transition hover:border-rose-300"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="space-y-0.5">
                      <h4 className="text-sm font-bold text-slate-800 flex items-center gap-2">
                        <span className="text-rose-600 text-xs font-mono font-bold">{index + 1}.</span>
                        <span>{con.theme}</span>
                      </h4>
                      <p className="text-[11px] text-slate-500">
                        Mentioned in: <strong className="text-rose-700 font-bold">{con.review_count.toLocaleString()} reviews</strong> ({con.percentage}% of reviews)
                      </p>
                    </div>

                    <button
                      onClick={() => handleOpenEvidence(con, 'con')}
                      className="inline-flex items-center gap-1 rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-1 text-[11px] font-semibold text-indigo-600 hover:bg-indigo-50 hover:border-indigo-200 transition shrink-0"
                      title="View supporting reviews from dataset"
                    >
                      <ExternalLink className="h-3 w-3" />
                      <span>Evidence</span>
                    </button>
                  </div>

                  {/* Example actual reviews */}
                  {con.example_reviews && con.example_reviews.length > 0 && (
                    <div className="space-y-1.5 pt-2 border-t border-slate-100">
                      <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">
                        Customer Quote:
                      </span>
                      {con.example_reviews.map((ex, i) => (
                        <p key={i} className="text-xs text-slate-600 italic line-clamp-2">
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

      {/* Evidence Modal */}
      {activeThemeModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-sm animate-fadeIn">
          <div className="relative w-full max-w-2xl max-h-[85vh] rounded-2xl bg-white border border-slate-200 p-6 shadow-2xl flex flex-col space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <div className="flex items-center gap-2">
                {activeThemeModal.type === 'pro' ? (
                  <CheckCircle2 className="h-5 w-5 text-emerald-600" />
                ) : (
                  <XCircle className="h-5 w-5 text-rose-600" />
                )}
                <div>
                  <h3 className="text-base font-bold text-slate-900">
                    Supporting Dataset Reviews for "{activeThemeModal.theme.theme}"
                  </h3>
                  <p className="text-xs text-slate-500">
                    {activeThemeModal.theme.review_count} reviews ({activeThemeModal.theme.percentage}%) matched
                  </p>
                </div>
              </div>

              <button
                onClick={() => setActiveThemeModal(null)}
                className="p-1.5 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto space-y-3 pr-1">
              {loadingEvidence ? (
                <div className="py-12 text-center space-y-2">
                  <div className="inline-block h-6 w-6 animate-spin rounded-full border-2 border-indigo-600 border-t-transparent" />
                  <p className="text-xs text-slate-500">Loading exact customer reviews...</p>
                </div>
              ) : evidenceReviews.length === 0 ? (
                <p className="text-center text-xs text-slate-500 py-8">
                  No direct matching review rows found for this theme.
                </p>
              ) : (
                evidenceReviews.map((rev) => (
                  <div
                    key={rev.id}
                    className="rounded-xl border border-slate-200 bg-slate-50/50 p-4 space-y-2"
                  >
                    <div className="flex items-center justify-between text-xs">
                      {renderStars(rev.rating)}
                      <span className="font-mono text-slate-400 text-[10px]">
                        Review #{rev.id}
                      </span>
                    </div>
                    <p className="text-xs text-slate-700 leading-relaxed">
                      "{rev.review_text}"
                    </p>
                  </div>
                ))
              )}
            </div>

            <div className="border-t border-slate-100 pt-3 flex justify-end">
              <button
                onClick={() => setActiveThemeModal(null)}
                className="secondary-button px-5 py-2 text-xs font-semibold"
              >
                Close Evidence
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
