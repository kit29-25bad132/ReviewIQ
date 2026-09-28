import React, { useEffect, useState } from 'react';
import {
  Compass,
  Sparkles,
  CheckCircle2,
  ArrowRight,
  Award,
  HelpCircle,
  BarChart3,
  Tag,
  ShieldCheck,
  AlertTriangle,
  Play,
  RotateCcw,
} from 'lucide-react';
import {
  PersonalizedRecommendationResponse,
  ProductSummary,
} from '../types/ecommerce';
import { getPersonalizedRecommendation } from '../services/api';

interface PersonalizedRecommendationProps {
  productId: string;
  productTitle: string;
  onSelectAlternativeProduct?: (product: ProductSummary) => void;
}

const PERSONA_OPTIONS = [
  { id: 'General User', label: '🌟 General User', desc: 'Balanced everyday use & reliability' },
  { id: 'Student', label: '🎓 Student', desc: 'Value for money, budget & durability' },
  { id: 'Gamer', label: '🎮 Gamer', desc: 'Maximum performance & fast responsiveness' },
  { id: 'Professional', label: '💼 Professional', desc: 'High build quality, consistency & reliability' },
  { id: 'Content Creator', label: '🎨 Content Creator', desc: 'Quality output, versatility & durability' },
  { id: 'Photographer', label: '📸 Enthusiast', desc: 'Premium build, optics & precision' },
];

const POPULAR_PRIORITIES = [
  'Performance',
  'Quality & Durability',
  'Value for Money',
  'Ease of Use',
  'Product Reliability',
  'Fast Shipping',
];

export const PersonalizedRecommendation: React.FC<PersonalizedRecommendationProps> = ({
  productId,
  productTitle,
  onSelectAlternativeProduct,
}) => {
  const [selectedPersona, setSelectedPersona] = useState<string>('General User');
  const [evaluatedPersona, setEvaluatedPersona] = useState<string | null>(null);
  const [customReq, setCustomReq] = useState<string>('');
  const [selectedPriorities, setSelectedPriorities] = useState<string[]>([
    'Quality & Durability',
    'Value for Money',
  ]);
  const [data, setData] = useState<PersonalizedRecommendationResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [analysisPhase, setAnalysisPhase] = useState<number>(1);
  const [error, setError] = useState<string>('');

  const triggerAnalysis = async (
    targetPersona: string = selectedPersona,
    targetPriorities: string[] = selectedPriorities,
    targetCustom: string = customReq
  ) => {
    setLoading(true);
    setError('');
    setAnalysisPhase(1);

    const timer1 = setTimeout(() => setAnalysisPhase(2), 700);
    const timer2 = setTimeout(() => setAnalysisPhase(3), 1500);

    try {
      const [res] = await Promise.all([
        getPersonalizedRecommendation(productId, {
          persona: targetPersona,
          priorities: targetPriorities,
          custom_requirements: targetCustom.trim() || undefined,
        }),
        new Promise((resolve) => setTimeout(resolve, 1800)),
      ]);
      setData(res);
      setEvaluatedPersona(targetPersona);
    } catch (err: unknown) {
      const msg =
        err instanceof Error
          ? err.message
          : 'Failed to generate personalized recommendation.';
      setError(msg);
    } finally {
      clearTimeout(timer1);
      clearTimeout(timer2);
      setLoading(false);
    }
  };

  // Initial load for baseline 'General User'
  useEffect(() => {
    setSelectedPersona('General User');
    setSelectedPriorities(['Quality & Durability', 'Value for Money']);
    setCustomReq('');
    triggerAnalysis('General User', ['Quality & Durability', 'Value for Money'], '');
  }, [productId]);

  const handlePersonaClick = (pId: string) => {
    setSelectedPersona(pId);
    let defaults = ['Quality & Durability', 'Value for Money'];
    if (pId === 'Gamer') defaults = ['Performance', 'Quality & Durability'];
    if (pId === 'Student') defaults = ['Value for Money', 'Ease of Use'];
    if (pId === 'Professional') defaults = ['Quality & Durability', 'Product Reliability'];
    if (pId === 'Content Creator') defaults = ['Performance', 'Quality & Durability'];
    if (pId === 'Photographer') defaults = ['Quality & Durability', 'Performance'];
    setSelectedPriorities(defaults);
    // Explicitly do NOT auto-trigger analysis here. User will click the Analyze button.
  };

  const togglePriority = (prio: string) => {
    let next: string[];
    if (selectedPriorities.includes(prio)) {
      next = selectedPriorities.filter((p) => p !== prio);
    } else {
      next = [...selectedPriorities, prio];
    }
    setSelectedPriorities(next);
  };

  const handleApplyRequirements = (e: React.FormEvent) => {
    e.preventDefault();
    triggerAnalysis(selectedPersona, selectedPriorities, customReq);
  };

  const isPending = !evaluatedPersona || evaluatedPersona !== selectedPersona;

  return (
    <div className="space-y-6">
      {/* Section Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-200 pb-3">
        <div>
          <h2 className="text-xl font-bold text-slate-900 flex items-center gap-2">
            <Compass className="h-5 w-5 text-indigo-600" />
            <span>Personalized Suitability & Recommendation Engine</span>
          </h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Evaluate product fit and explore alternative peer recommendations grounded strictly in verified buyer reviews.
          </p>
        </div>

        <span className="rounded-full bg-indigo-50 border border-indigo-100 px-3 py-1 text-xs font-semibold text-indigo-700 flex items-center gap-1.5 self-start sm:self-center">
          <Sparkles className="h-3.5 w-3.5 text-indigo-600" />
          <span>Real-time AI Lens</span>
        </span>
      </div>

      {/* 1. User Profile & Requirements Input Form */}
      <div className="modern-card p-6 space-y-5">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div>
            <h3 className="text-sm font-bold text-slate-900 mb-1 flex items-center gap-2">
              <Tag className="h-4 w-4 text-indigo-600" />
              <span>1. Select User Profile & Tailor Priorities</span>
            </h3>
            <p className="text-xs text-slate-500">
              Select a target profile and click <strong className="text-indigo-600 font-semibold">Analyze Suitability</strong> to evaluate authentic buyer reviews for <span className="font-semibold text-slate-700">{productTitle}</span>.
            </p>
          </div>

          {isPending && (
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-amber-50 border border-amber-200 text-amber-800 text-[11px] font-bold self-start sm:self-auto animate-pulse">
              <span>● Pending Analysis for {selectedPersona}</span>
            </span>
          )}
        </div>

        {/* Persona Preset Buttons */}
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
          {PERSONA_OPTIONS.map((p) => {
            const isSelected = selectedPersona === p.id;
            return (
              <button
                key={p.id}
                type="button"
                onClick={() => handlePersonaClick(p.id)}
                className={`rounded-2xl border p-3.5 text-left transition-all duration-200 cursor-pointer ${
                  isSelected
                    ? 'border-indigo-600 bg-indigo-50/90 text-indigo-950 shadow-md shadow-indigo-500/10 ring-2 ring-indigo-300 translate-y-[-1px]'
                    : 'border-slate-200 bg-white text-slate-600 hover:border-slate-300 hover:bg-slate-50'
                }`}
              >
                <div className="text-xs font-bold">{p.label}</div>
                <div className="text-[10px] text-slate-500 mt-1 line-clamp-1">{p.desc}</div>
              </button>
            );
          })}
        </div>

        {/* Priority Checkbox Pills & Custom Requirements */}
        <form onSubmit={handleApplyRequirements} className="space-y-4 pt-3 border-t border-slate-100">
          <div>
            <label className="text-xs font-bold text-slate-600 uppercase tracking-wider block mb-2">
              Features & Priorities of Interest:
            </label>
            <div className="flex flex-wrap gap-2">
              {POPULAR_PRIORITIES.map((prio) => {
                const active = selectedPriorities.includes(prio);
                return (
                  <button
                    key={prio}
                    type="button"
                    onClick={() => togglePriority(prio)}
                    className={`rounded-xl border px-3 py-1.5 text-xs font-bold transition-all ${
                      active
                        ? 'border-indigo-600 bg-indigo-600 text-white shadow-xs'
                        : 'border-slate-200 bg-white text-slate-600 hover:border-slate-300 hover:bg-slate-50'
                    }`}
                  >
                    {active ? '✓ ' : '+ '}
                    {prio}
                  </button>
                );
              })}
            </div>
          </div>

          <div className="flex flex-col sm:flex-row gap-3">
            <input
              type="text"
              value={customReq}
              onChange={(e) => setCustomReq(e.target.value)}
              placeholder="e.g. Need durable materials for travel with high reliability..."
              className="flex-1 rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-xs text-slate-800 placeholder-slate-400 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 focus:outline-none transition"
            />
            <button
              type="submit"
              disabled={loading}
              className="primary-button inline-flex items-center justify-center gap-2 px-5 py-2.5 text-xs font-bold shrink-0 shadow-md shadow-indigo-500/20"
            >
              <Sparkles className="h-3.5 w-3.5" />
              <span>Analyze Suitability for {selectedPersona}</span>
            </button>
          </div>
        </form>
      </div>

      {/* 2. Loading State with Multi-Phase Animation */}
      {loading ? (
        <div className="modern-card p-12 text-center space-y-4 animate-fadeIn border border-indigo-100 bg-gradient-to-b from-indigo-50/30 to-white">
          <div className="inline-block h-9 w-9 animate-spin rounded-full border-3 border-indigo-600 border-t-transparent" />
          <div className="space-y-1 max-w-lg mx-auto">
            <p className="text-sm font-bold text-slate-900">
              {analysisPhase === 1 && `Filtering dataset reviews for ${selectedPersona} criteria...`}
              {analysisPhase === 2 && `Scoring priority matches (${selectedPriorities.slice(0, 2).join(', ')})...`}
              {analysisPhase === 3 && `Synthesizing ${selectedPersona} suitability verdict...`}
            </p>
            <p className="text-xs text-slate-500">
              Evaluating real customer sentiment and computing category benchmark rankings...
            </p>
          </div>
          <div className="w-48 h-1.5 bg-slate-100 rounded-full mx-auto overflow-hidden">
            <div
              className="h-full bg-[#5B50E5] transition-all duration-500 rounded-full"
              style={{ width: `${(analysisPhase / 3) * 100}%` }}
            />
          </div>
        </div>
      ) : isPending ? (
        /* Prompt Card when user switched persona or priorities but hasn't clicked Analyze yet */
        <div className="modern-card p-8 sm:p-10 text-center space-y-4 border-2 border-dashed border-indigo-200 bg-indigo-50/30 animate-fadeIn">
          <div className="h-12 w-12 rounded-2xl bg-indigo-100 text-indigo-600 flex items-center justify-center mx-auto shadow-xs">
            <Play className="h-6 w-6 ml-0.5" />
          </div>
          <div className="max-w-md mx-auto space-y-1.5">
            <h4 className="text-base font-extrabold text-slate-900">
              Ready to Evaluate for {selectedPersona} Profile
            </h4>
            <p className="text-xs text-slate-600 leading-relaxed">
              Target Priorities: <span className="font-semibold text-indigo-700">{selectedPriorities.join(', ')}</span>.
              <br />
              Click the button below to process verified customer reviews and calculate authentic suitability for <span className="font-semibold">{selectedPersona}s</span>.
            </p>
          </div>
          <div className="pt-2">
            <button
              type="button"
              onClick={() => triggerAnalysis()}
              className="primary-button inline-flex items-center gap-2 px-6 py-3 text-xs font-bold shadow-md shadow-indigo-500/25 cursor-pointer hover:scale-[1.02] transition"
            >
              <Sparkles className="h-4 w-4" />
              <span>Analyze Suitability for {selectedPersona}</span>
            </button>
          </div>
        </div>
      ) : error || !data ? (
        <div className="rounded-2xl border border-rose-200 bg-rose-50 p-6 text-center text-xs text-rose-700">
          {error || 'Unable to generate recommendation comparison.'}
        </div>
      ) : (
        <div className="space-y-6 animate-fadeIn">
          {/* 2. SUITABILITY ASSESSMENT RESULT */}
          <div className="modern-card p-6 space-y-5">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                <HelpCircle className="h-4 w-4 text-indigo-600" />
                <span>Suitability Verdict & Persona Intelligence</span>
              </h3>
              <div className="flex items-center gap-2">
                <span className="rounded-full bg-indigo-50 text-indigo-700 border border-indigo-100 px-3 py-0.5 text-xs font-bold">
                  Profile: {evaluatedPersona}
                </span>
                <button
                  onClick={() => triggerAnalysis(selectedPersona, selectedPriorities, customReq)}
                  title="Re-run analysis"
                  className="p-1 rounded-lg text-slate-400 hover:text-indigo-600 hover:bg-slate-50 transition"
                >
                  <RotateCcw className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>

            <div className="rounded-2xl border border-slate-100 bg-gradient-to-br from-slate-50/80 to-indigo-50/20 p-5 space-y-4">
              <div className="flex items-start gap-3.5">
                <div className="rounded-xl p-2.5 bg-emerald-100 text-emerald-700 shrink-0 mt-0.5">
                  <CheckCircle2 className="h-5 w-5" />
                </div>
                <div className="space-y-1">
                  <h4 className="text-base font-extrabold text-slate-900">
                    {data.recommendation_headline || productTitle}
                  </h4>
                  <p className="text-xs text-slate-600 leading-relaxed font-medium">
                    {data.suitability_verdict}
                  </p>
                </div>
              </div>

              {/* Recommendation Reasons */}
              {data.recommendation_reasons && data.recommendation_reasons.length > 0 && (
                <div className="space-y-2 border-t border-slate-200/60 pt-3">
                  <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider block">
                    Key Evaluation Evidence:
                  </span>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                    {data.recommendation_reasons.map((reason, idx) => (
                      <div key={idx} className="flex items-start gap-2 text-xs text-slate-700 p-2.5 rounded-xl bg-white border border-slate-100 shadow-2xs">
                        <span className="text-indigo-600 font-bold mt-0.5">•</span>
                        <span className="leading-snug">{reason}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Suitable For & What to Consider */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2">
                {/* Pros / Suitable For */}
                <div className="p-4 rounded-xl bg-emerald-50/70 border border-emerald-100 space-y-2">
                  <div className="flex items-center gap-1.5 text-xs font-bold text-emerald-800">
                    <ShieldCheck className="h-4 w-4 text-emerald-600" />
                    <span>Why This Fits {evaluatedPersona}s</span>
                  </div>
                  <ul className="space-y-1 text-xs text-emerald-950">
                    {data.suitable_for?.map((item, idx) => (
                      <li key={idx} className="flex items-start gap-1.5">
                        <span className="text-emerald-600 font-bold">✓</span>
                        <span>{item}</span>
                      </li>
                    ))}
                  </ul>
                </div>

                {/* Considerations / Cons */}
                <div className="p-4 rounded-xl bg-amber-50/70 border border-amber-100 space-y-2">
                  <div className="flex items-center gap-1.5 text-xs font-bold text-amber-800">
                    <AlertTriangle className="h-4 w-4 text-amber-600" />
                    <span>Considerations & Caveats</span>
                  </div>
                  <ul className="space-y-1 text-xs text-amber-950">
                    {data.consider_before_buying?.map((item, idx) => (
                      <li key={idx} className="flex items-start gap-1.5">
                        <span className="text-amber-600 font-bold">!</span>
                        <span>{item}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>

              {/* Priority Matches Evidence */}
              {data.priority_matches && data.priority_matches.length > 0 && (
                <div className="space-y-2 pt-2">
                  <span className="text-[11px] uppercase tracking-wider text-slate-500 font-bold block">
                    Priority Alignment Breakdown:
                  </span>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                    {data.priority_matches.map((pm, i) => (
                      <div
                        key={i}
                        className="rounded-xl border border-slate-200 bg-white p-3.5 text-xs space-y-1.5 shadow-2xs"
                      >
                        <div className="flex items-center justify-between">
                          <span className="font-bold text-slate-800">{pm.priority}</span>
                          <span className="rounded-md px-2 py-0.5 text-[10px] uppercase font-bold bg-indigo-50 text-indigo-700 border border-indigo-100">
                            {pm.evidence_level}
                          </span>
                        </div>
                        <p className="text-[11px] text-slate-600 leading-relaxed">{pm.details}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* 3. SIDE-BY-SIDE RELATED COMPARISON TABLE */}
          {data.comparison_products && data.comparison_products.length > 0 && (
            <div className="modern-card p-6 space-y-4">
              <div className="flex items-center justify-between border-b border-slate-100 pb-3">
                <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                  <BarChart3 className="h-4 w-4 text-indigo-600" />
                  <span>Related Products Peer Comparison</span>
                </h3>
                <span className="text-xs text-slate-500 font-medium">
                  Category: {data.comparison_products[0]?.category || 'Related'}
                </span>
              </div>

              <div className="overflow-x-auto rounded-xl border border-slate-200">
                <table className="w-full text-left text-xs border-collapse">
                  <thead>
                    <tr className="border-b border-slate-200 bg-slate-50/80 text-slate-500 font-bold uppercase text-[10px]">
                      <th className="p-3.5">Product</th>
                      <th className="p-3.5">Rating</th>
                      <th className="p-3.5">Reviews</th>
                      <th className="p-3.5">Positive %</th>
                      <th className="p-3.5">Top Pros</th>
                      <th className="p-3.5">Top Cons</th>
                      <th className="p-3.5 text-right">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {data.comparison_products.map((item) => (
                      <tr
                        key={item.product_id}
                        className={`hover:bg-slate-50/70 transition ${
                          item.is_selected ? 'bg-indigo-50/40 font-semibold' : ''
                        }`}
                      >
                        <td className="p-3.5">
                          <div className="font-bold text-slate-900 flex items-center gap-1.5">
                            <span>{item.product_title}</span>
                            {item.is_selected && (
                              <span className="rounded-full bg-indigo-100 text-indigo-700 px-2 py-0.5 text-[9px] font-bold">
                                Current
                              </span>
                            )}
                          </div>
                          <span className="text-[10px] text-slate-400 font-normal">{item.category}</span>
                        </td>
                        <td className="p-3.5">
                          <div className="flex items-center gap-1 font-bold text-amber-500">
                            ★ {item.average_rating.toFixed(1)}
                          </div>
                        </td>
                        <td className="p-3.5 font-mono text-slate-600">
                          {item.review_count.toLocaleString()}
                        </td>
                        <td className="p-3.5">
                          <span className="text-emerald-700 font-bold bg-emerald-50 px-2 py-0.5 rounded-md text-[11px]">
                            {item.positive_percentage}%
                          </span>
                        </td>
                        <td className="p-3.5 text-slate-600">
                          {item.common_pros.slice(0, 2).join(', ') || 'Quality'}
                        </td>
                        <td className="p-3.5 text-slate-600">
                          {item.common_cons.slice(0, 2).join(', ') || 'Minor complaints'}
                        </td>
                        <td className="p-3.5 text-right">
                          {!item.is_selected && onSelectAlternativeProduct && (
                            <button
                              onClick={() =>
                                onSelectAlternativeProduct({
                                  product_id: item.product_id,
                                  product_title: item.product_title,
                                  category: item.category,
                                  review_count: item.review_count,
                                  average_rating: item.average_rating,
                                })
                              }
                              className="rounded-lg border border-indigo-200 bg-indigo-50 px-2.5 py-1 text-[11px] font-bold text-indigo-600 hover:bg-indigo-600 hover:text-white transition"
                            >
                              Analyze
                            </button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* 4. RECOMMENDED ALTERNATIVE */}
          {data.recommended_product && (
            <div className="modern-card p-6 space-y-4 border-indigo-100 bg-gradient-to-r from-indigo-50/30 to-white">
              <div className="flex items-center justify-between border-b border-indigo-100 pb-3">
                <h3 className="text-sm font-bold text-indigo-950 flex items-center gap-2">
                  <Award className="h-5 w-5 text-indigo-600" />
                  <span>Top-Ranked Peer Alternative</span>
                </h3>
                <span className="text-[10px] uppercase tracking-wider text-indigo-700 font-bold bg-indigo-100 px-2.5 py-0.5 rounded-full">
                  Category Best
                </span>
              </div>

              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div className="space-y-1">
                  <h4 className="text-base font-extrabold text-slate-900">
                    {data.recommended_product.product_title}
                  </h4>
                  <div className="flex items-center gap-3 text-xs text-slate-500 font-medium">
                    <span className="text-amber-500 font-bold">
                      ★ {data.recommended_product.average_rating.toFixed(1)} / 5.0
                    </span>
                    <span>·</span>
                    <span>{data.recommended_product.review_count.toLocaleString()} customer reviews</span>
                    <span>·</span>
                    <span className="text-slate-600">{data.recommended_product.category}</span>
                  </div>
                </div>

                {onSelectAlternativeProduct && (
                  <button
                    onClick={() => onSelectAlternativeProduct(data.recommended_product)}
                    className="primary-button inline-flex items-center gap-2 px-5 py-2.5 text-xs font-bold shrink-0"
                  >
                    <span>Inspect Alternative</span>
                    <ArrowRight className="h-3.5 w-3.5" />
                  </button>
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
