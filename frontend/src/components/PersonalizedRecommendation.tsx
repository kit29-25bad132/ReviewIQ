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
  { id: 'Content Creator', label: '🎨 Content Creator', desc: 'Quality output, durability & features' },
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
  const [persona, setPersona] = useState<string>('General User');
  const [customReq, setCustomReq] = useState<string>('');
  const [selectedPriorities, setSelectedPriorities] = useState<string[]>([
    'Quality & Durability',
    'Value for Money',
  ]);
  const [data, setData] = useState<PersonalizedRecommendationResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string>('');

  const fetchRecommendation = (
    currentPersona: string = persona,
    currentPriorities: string[] = selectedPriorities,
    currentCustom: string = customReq
  ) => {
    setLoading(true);
    setError('');
    getPersonalizedRecommendation(productId, {
      persona: currentPersona,
      priorities: currentPriorities,
      custom_requirements: currentCustom.trim() || undefined,
    })
      .then((res) => {
        setData(res);
      })
      .catch((err: unknown) => {
        const msg = err instanceof Error ? err.message : 'Failed to generate personalized recommendation.';
        setError(msg);
      })
      .finally(() => {
        setLoading(false);
      });
  };

  useEffect(() => {
    fetchRecommendation('General User', ['Quality & Durability', 'Value for Money'], '');
  }, [productId]);

  const handlePersonaClick = (pId: string) => {
    setPersona(pId);
    let defaults = ['Quality & Durability', 'Value for Money'];
    if (pId === 'Gamer') defaults = ['Performance', 'Quality & Durability'];
    if (pId === 'Student') defaults = ['Value for Money', 'Ease of Use'];
    if (pId === 'Professional') defaults = ['Quality & Durability', 'Product Reliability'];
    if (pId === 'Content Creator') defaults = ['Performance', 'Quality & Durability'];
    setSelectedPriorities(defaults);
    fetchRecommendation(pId, defaults, customReq);
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
    fetchRecommendation(persona, selectedPriorities, customReq);
  };

  return (
    <div className="space-y-6">
      {/* Section Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-[#292A2B] pb-3">
        <div>
          <h2 className="text-lg font-medium text-[#F5F2EA] flex items-center gap-2">
            <Compass className="h-4 w-4 text-[#D4AF5A]" />
            Personalized Product Recommendation & Decision Engine
          </h2>
          <p className="text-xs text-[#74736E]">
            Tailored analysis based strictly on your stated priorities and verified dataset review evidence.
          </p>
        </div>

        <span className="rounded-full border border-[#D4AF5A]/30 bg-[#1B1915] px-3 py-1 text-[10px] font-mono text-[#D4AF5A] flex items-center gap-1.5 self-start sm:self-center">
          <Sparkles className="h-3.5 w-3.5 text-[#D4AF5A]" />
          <span>Category Benchmarking</span>
        </span>
      </div>

      {/* 1. User Profile & Requirements Input Form */}
      <div className="premium-panel p-6 space-y-5">
        <div>
          <h3 className="text-sm font-medium text-[#F5F2EA] mb-1 flex items-center gap-2">
            <Tag className="h-4 w-4 text-[#D4AF5A]" />
            1. Select Your User Profile or Customize Priorities
          </h3>
          <p className="text-xs text-[#74736E]">
            Choose a profile below or enter custom requirements to match this product against peer alternatives in {productTitle}'s category.
          </p>
        </div>

        {/* Persona Preset Buttons */}
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2.5">
          {PERSONA_OPTIONS.map((p) => (
            <button
              key={p.id}
              type="button"
              onClick={() => handlePersonaClick(p.id)}
              className={`rounded-xl border p-3 text-left transition ${
                persona === p.id
                  ? 'border-[#D4AF5A] bg-[#1B1915] text-[#F5F2EA] shadow-[0_0_20px_rgba(212,175,90,0.2)]'
                  : 'border-[#292A2B] bg-[#151617] text-[#AAA79F] hover:border-[#D4AF5A]/30 hover:bg-[#1C1D1F]'
              }`}
            >
              <div className="text-xs font-semibold">{p.label}</div>
              <div className="text-[10px] text-[#74736E] mt-1 line-clamp-1">{p.desc}</div>
            </button>
          ))}
        </div>

        {/* Priority Checkbox Pills & Custom Requirements */}
        <form onSubmit={handleApplyRequirements} className="space-y-4 pt-3 border-t border-[#292A2B]">
          <div>
            <label className="text-xs uppercase tracking-wider text-[#74736E] block mb-2 font-medium">
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
                    className={`rounded-lg border px-3 py-1 text-xs font-medium transition ${
                      active
                        ? 'border-[#D4AF5A] bg-[#1B1915] text-[#F0D58A]'
                        : 'border-[#292A2B] bg-[#151617] text-[#AAA79F] hover:border-[#D4AF5A]/30 hover:text-[#F5F2EA]'
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
              placeholder="e.g. I need something durable for daily use with long battery life..."
              className="flex-1 rounded-xl border border-[#292A2B] bg-[#151617] px-4 py-2.5 text-xs text-[#F5F2EA] placeholder-[#74736E] focus:border-[#D4AF5A]/60 focus:outline-none"
            />
            <button
              type="submit"
              disabled={loading}
              className="gold-button inline-flex items-center justify-center gap-2 px-5 py-2.5 text-xs disabled:opacity-50"
            >
              <Sparkles className="h-3.5 w-3.5" />
              <span>Update Recommendation</span>
            </button>
          </div>
        </form>
      </div>

      {loading ? (
        <div className="premium-panel p-16 text-center space-y-3">
          <div className="inline-block h-6 w-6 animate-spin rounded-full border-2 border-[#D4AF5A] border-t-transparent" />
          <p className="text-xs text-[#AAA79F]">
            Comparing category alternatives & matching dataset review evidence...
          </p>
        </div>
      ) : error || !data ? (
        <div className="rounded-xl border border-rose-900/40 bg-rose-950/20 p-6 text-center text-xs text-rose-300">
          {error || 'Unable to generate recommendation comparison.'}
        </div>
      ) : (
        <div className="space-y-6">
          {/* 2. SUITABILITY ASSESSMENT */}
          <div className="premium-panel p-6 space-y-4">
            <div className="flex items-center justify-between border-b border-[#292A2B] pb-3">
              <h3 className="text-sm font-medium text-[#F5F2EA] flex items-center gap-2">
                <HelpCircle className="h-4 w-4 text-[#D4AF5A]" />
                Suitability Verdict & Intelligence
              </h3>
              <span className="text-xs text-[#74736E]">
                Persona: {persona}
              </span>
            </div>

            <div className="rounded-xl border border-[#292A2B] bg-[#151617] p-5 space-y-4">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div className="flex items-center gap-3">
                  <div className="rounded-xl p-3 border border-[#D4AF5A]/40 bg-[#1B1915] text-[#D4AF5A]">
                    <CheckCircle2 className="h-6 w-6" />
                  </div>
                  <div>
                    <span className="text-xs uppercase font-semibold tracking-wider text-[#D4AF5A]">
                      {data.suitability_verdict || 'Analysis Complete'}
                    </span>
                    <h4 className="text-base font-medium text-[#F5F2EA] mt-0.5">
                      {data.recommendation_headline || productTitle}
                    </h4>
                  </div>
                </div>
              </div>

              {/* Recommendation Reasons */}
              {data.recommendation_reasons && data.recommendation_reasons.length > 0 && (
                <div className="space-y-1.5 border-t border-[#292A2B] pt-3">
                  {data.recommendation_reasons.map((reason, idx) => (
                    <p key={idx} className="text-xs text-[#AAA79F] leading-relaxed">
                      • {reason}
                    </p>
                  ))}
                </div>
              )}

              {/* Priority Matches Evidence */}
              {data.priority_matches && data.priority_matches.length > 0 && (
                <div className="space-y-2 pt-2">
                  <span className="text-[10px] uppercase tracking-wider text-[#74736E] font-medium">
                    Priority Alignment Breakdown:
                  </span>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    {data.priority_matches.map((pm, i) => (
                      <div
                        key={i}
                        className="rounded-lg border border-[#292A2B] bg-[#111213] p-3 text-xs space-y-1"
                      >
                        <div className="flex items-center justify-between">
                          <span className="font-medium text-[#F5F2EA]">{pm.priority}</span>
                          <span className="rounded px-1.5 py-0.5 text-[10px] uppercase font-semibold bg-[#1B1915] text-[#D4AF5A] border border-[#D4AF5A]/30">
                            {pm.evidence_level}
                          </span>
                        </div>
                        <p className="text-[11px] text-[#74736E]">{pm.details}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* 3. SIDE-BY-SIDE RELATED COMPARISON TABLE */}
          {data.comparison_products && data.comparison_products.length > 0 && (
            <div className="premium-panel p-6 space-y-4">
              <div className="flex items-center justify-between border-b border-[#292A2B] pb-3">
                <h3 className="text-sm font-medium text-[#F5F2EA] flex items-center gap-2">
                  <BarChart3 className="h-4 w-4 text-[#D4AF5A]" />
                  Related Products Side-by-Side Comparison
                </h3>
                <span className="text-xs text-[#74736E]">
                  Same Category ({data.comparison_products[0]?.category || 'Related'})
                </span>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs border-collapse">
                  <thead>
                    <tr className="border-b border-[#292A2B] text-[#74736E]">
                      <th className="p-3">Product</th>
                      <th className="p-3">Rating</th>
                      <th className="p-3">Reviews</th>
                      <th className="p-3">Sentiment</th>
                      <th className="p-3">Top Pros</th>
                      <th className="p-3">Top Cons</th>
                      <th className="p-3 text-right">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#292A2B]/60">
                    {data.comparison_products.map((item) => (
                      <tr
                        key={item.product_id}
                        className={`hover:bg-[#1C1D1F] transition ${
                          item.is_selected ? 'bg-[#1B1915]' : ''
                        }`}
                      >
                        <td className="p-3">
                          <div className="font-medium text-[#F5F2EA] flex items-center gap-1.5">
                            <span>{item.product_title}</span>
                            {item.is_selected && (
                              <span className="rounded bg-[#D4AF5A]/20 border border-[#D4AF5A]/40 px-1.5 py-0.5 text-[9px] text-[#D4AF5A]">
                                Current
                              </span>
                            )}
                          </div>
                          <span className="text-[10px] text-[#74736E]">{item.category}</span>
                        </td>
                        <td className="p-3">
                          <div className="flex items-center gap-1 font-semibold text-[#D4AF5A]">
                            ★ {item.average_rating.toFixed(1)}
                          </div>
                        </td>
                        <td className="p-3 font-mono text-[#AAA79F]">
                          {item.review_count.toLocaleString()}
                        </td>
                        <td className="p-3">
                          <span className="text-emerald-400 font-medium">
                            {item.positive_percentage}% Pos
                          </span>
                        </td>
                        <td className="p-3 text-[#AAA79F]">
                          {item.common_pros.slice(0, 2).join(', ') || 'N/A'}
                        </td>
                        <td className="p-3 text-[#AAA79F]">
                          {item.common_cons.slice(0, 2).join(', ') || 'N/A'}
                        </td>
                        <td className="p-3 text-right">
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
                              className="rounded-lg border border-[#292A2B] bg-[#151617] px-2.5 py-1 text-[11px] font-medium text-[#D4AF5A] hover:border-[#D4AF5A]/40 hover:bg-[#1C1D1F] transition"
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
            <div className="rounded-xl border border-[#D4AF5A]/40 bg-[#171613] p-6 space-y-4">
              <div className="flex items-center justify-between border-b border-[#D4AF5A]/20 pb-3">
                <h3 className="text-sm font-semibold text-[#F0D58A] flex items-center gap-2">
                  <Award className="h-5 w-5 text-[#D4AF5A]" />
                  Recommended Category Match
                </h3>
                <span className="text-[10px] uppercase tracking-wider text-[#D4AF5A] font-semibold">
                  Peer Match
                </span>
              </div>

              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div className="space-y-1">
                  <h4 className="text-base font-semibold text-[#F5F2EA]">
                    {data.recommended_product.product_title}
                  </h4>
                  <div className="flex items-center gap-3 text-xs text-[#AAA79F]">
                    <span className="text-[#D4AF5A] font-medium">
                      ★ {data.recommended_product.average_rating.toFixed(1)}/5
                    </span>
                    <span>·</span>
                    <span>{data.recommended_product.review_count.toLocaleString()} reviews</span>
                    <span>·</span>
                    <span>{data.recommended_product.category}</span>
                  </div>
                </div>

                {onSelectAlternativeProduct && (
                  <button
                    onClick={() => onSelectAlternativeProduct(data.recommended_product)}
                    className="gold-button inline-flex items-center gap-2 px-5 py-2.5 text-xs font-semibold shrink-0"
                  >
                    <span>View Full Analysis</span>
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
