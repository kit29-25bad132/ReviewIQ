import React, { useEffect, useState } from 'react';
import {
  Compass,
  Sparkles,
  CheckCircle2,
  AlertTriangle,
  Star,
  ArrowRight,
  ShieldCheck,
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
      .catch((err) => {
        setError(
          err.response?.data?.detail || 'Failed to generate personalized recommendation.'
        );
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

  return (
    <div className="space-y-8">
      {/* Section Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-800 pb-4">
        <div>
          <h2 className="text-lg font-bold text-white flex items-center gap-2">
            <Compass className="h-5 w-5 text-purple-400" />
            Personalized Product Recommendation & Decision Engine
          </h2>
          <p className="text-xs text-slate-400">
            Tailored analysis based strictly on your stated priorities and verified dataset review evidence.
          </p>
        </div>

        <span className="rounded-full bg-indigo-500/10 border border-indigo-500/30 px-3 py-1 text-[11px] font-mono text-indigo-300 flex items-center gap-1.5 self-start sm:self-center">
          <Sparkles className="h-3.5 w-3.5 text-indigo-400" />
          <span>Multi-Product Category Benchmarking</span>
        </span>
      </div>

      {/* 1. User Profile & Requirements Input Form */}
      <div className="rounded-2xl border border-purple-500/30 bg-[#111827]/90 p-6 backdrop-blur-xl shadow-glass space-y-5">
        <div>
          <h3 className="text-sm font-bold text-white mb-2 flex items-center gap-2">
            <Tag className="h-4 w-4 text-cyan-400" />
            1. Select Your User Profile or Customize Priorities
          </h3>
          <p className="text-xs text-slate-400">
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
                  ? 'border-purple-500 bg-purple-600/20 text-white shadow-glow-purple'
                  : 'border-slate-800 bg-[#0B0F17] text-slate-300 hover:border-slate-700 hover:bg-slate-800/40'
              }`}
            >
              <div className="text-xs font-bold">{p.label}</div>
              <div className="text-[10px] text-slate-400 mt-1 line-clamp-1">{p.desc}</div>
            </button>
          ))}
        </div>

        {/* Priority Checkbox Pills & Custom Requirements */}
        <form onSubmit={handleApplyRequirements} className="space-y-4 pt-2 border-t border-slate-800/80">
          <div>
            <label className="text-xs font-mono uppercase text-slate-400 block mb-2">
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
                        ? 'border-cyan-500/40 bg-cyan-500/20 text-cyan-200'
                        : 'border-slate-800 bg-slate-900 text-slate-400 hover:border-slate-700 hover:text-slate-200'
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
              placeholder="e.g. I need something durable for daily travel with great battery life..."
              className="flex-1 rounded-xl border border-slate-700 bg-[#0B0F17] px-4 py-2.5 text-xs text-white placeholder-slate-500 focus:border-purple-500 focus:outline-none"
            />
            <button
              type="submit"
              disabled={loading}
              className="inline-flex items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-purple-600 via-indigo-600 to-cyan-500 px-5 py-2.5 text-xs font-semibold text-white shadow-md hover:brightness-110 disabled:opacity-50 transition"
            >
              <Sparkles className="h-3.5 w-3.5" />
              <span>Update Recommendation</span>
            </button>
          </div>
        </form>
      </div>

      {loading ? (
        <div className="rounded-2xl border border-white/10 bg-[#111827]/80 p-16 text-center space-y-3">
          <div className="inline-block h-8 w-8 animate-spin rounded-full border-2 border-purple-400 border-t-transparent" />
          <p className="text-xs text-slate-400 font-mono">
            Comparing category alternatives & matching dataset review evidence...
          </p>
        </div>
      ) : error || !data ? (
        <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 p-6 text-center text-xs text-rose-300">
          {error || 'Unable to generate recommendation comparison.'}
        </div>
      ) : (
        <div className="space-y-8 animate-fadeIn">
          {/* 2. IS THIS PRODUCT SUITABLE FOR YOU? */}
          <div className="rounded-2xl border border-white/10 bg-[#111827]/85 p-6 backdrop-blur-xl shadow-glass space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 className="text-sm font-bold text-white flex items-center gap-2">
                <HelpCircle className="h-4 w-4 text-cyan-400" />
                IS THIS PRODUCT SUITABLE FOR YOU?
              </h3>
              <span className="text-xs font-mono text-slate-400">
                Persona: <strong className="text-purple-300">{persona}</strong>
              </span>
            </div>

            {/* Verdict Box */}
            <div className="rounded-xl border border-indigo-500/30 bg-indigo-950/25 p-4 text-xs sm:text-sm text-indigo-200 leading-relaxed font-medium">
              {data.suitability_verdict}
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-1">
              {/* Suitable for */}
              <div className="rounded-xl border border-emerald-500/20 bg-emerald-950/20 p-4 space-y-2">
                <div className="text-xs font-bold text-emerald-400 flex items-center gap-1.5">
                  <CheckCircle2 className="h-4 w-4" />
                  <span>✓ Suitable For:</span>
                </div>
                <ul className="space-y-1.5 text-xs text-slate-300">
                  {data.suitable_for.map((item, idx) => (
                    <li key={idx} className="flex items-start gap-2">
                      <span className="text-emerald-400 font-bold">•</span>
                      <span>{item}</span>
                    </li>
                  ))}
                </ul>
              </div>

              {/* Consider before buying */}
              <div className="rounded-xl border border-amber-500/20 bg-amber-950/20 p-4 space-y-2">
                <div className="text-xs font-bold text-amber-400 flex items-center gap-1.5">
                  <AlertTriangle className="h-4 w-4" />
                  <span>⚠ Consider Before Buying:</span>
                </div>
                <ul className="space-y-1.5 text-xs text-slate-300">
                  {data.consider_before_buying.map((item, idx) => (
                    <li key={idx} className="flex items-start gap-2">
                      <span className="text-amber-400 font-bold">•</span>
                      <span>{item}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </div>

          {/* 3. SIDE-BY-SIDE PRODUCT COMPARISON TABLE */}
          <div className="rounded-2xl border border-white/10 bg-[#111827]/85 p-6 backdrop-blur-xl shadow-glass space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-800 pb-3">
              <h3 className="text-sm font-bold text-white flex items-center gap-2">
                <BarChart3 className="h-4 w-4 text-purple-400" />
                COMPARE WITH SIMILAR PRODUCTS ({data.selected_product.category} Category)
              </h3>
              <span className="text-[11px] font-mono text-slate-400">
                Real Dataset Metrics Only
              </span>
            </div>

            {data.comparison_products && data.comparison_products.filter((item) => !item.is_selected).length > 0 ? (
              <div className="overflow-x-auto rounded-xl border border-slate-800 bg-[#0B0F17]">
                <table className="w-full text-left text-xs">
                  <thead className="border-b border-slate-800 bg-slate-900/80 text-slate-400 font-mono uppercase text-[10px]">
                    <tr>
                      <th className="p-3.5 w-36">Metric / Feature</th>
                      {data.comparison_products.map((item) => (
                        <th
                          key={item.product_id}
                          className={`p-3.5 min-w-[200px] ${
                            item.is_selected
                              ? 'bg-purple-950/40 text-purple-300 border-x border-purple-500/30'
                              : 'text-slate-200'
                          }`}
                        >
                          <div className="font-bold text-xs">{item.product_title}</div>
                          <div className="text-[10px] font-mono opacity-70">
                            {item.is_selected ? '★ Selected Product' : `ID: ${item.product_id}`}
                          </div>
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/80 font-mono">
                    {/* Rating */}
                    <tr>
                      <td className="p-3 text-slate-400 font-sans font-medium">Average Rating</td>
                      {data.comparison_products.map((item) => (
                        <td
                          key={item.product_id}
                          className={`p-3 ${item.is_selected ? 'bg-purple-950/20 border-x border-purple-500/20' : ''}`}
                        >
                          <div className="flex items-center gap-2">
                            {renderStars(item.average_rating)}
                            <span className="font-bold text-amber-400">{item.average_rating} / 5</span>
                          </div>
                        </td>
                      ))}
                    </tr>

                    {/* Total Reviews */}
                    <tr>
                      <td className="p-3 text-slate-400 font-sans font-medium">Verified Reviews</td>
                      {data.comparison_products.map((item) => (
                        <td
                          key={item.product_id}
                          className={`p-3 font-semibold text-white ${
                            item.is_selected ? 'bg-purple-950/20 border-x border-purple-500/20' : ''
                          }`}
                        >
                          {item.review_count.toLocaleString()} reviews
                        </td>
                      ))}
                    </tr>

                    {/* Positive Sentiment */}
                    <tr>
                      <td className="p-3 text-slate-400 font-sans font-medium">Positive Sentiment</td>
                      {data.comparison_products.map((item) => (
                        <td
                          key={item.product_id}
                          className={`p-3 text-emerald-400 font-bold ${
                            item.is_selected ? 'bg-purple-950/20 border-x border-purple-500/20' : ''
                          }`}
                        >
                          {item.positive_percentage}%
                        </td>
                      ))}
                    </tr>

                    {/* Negative Sentiment */}
                    <tr>
                      <td className="p-3 text-slate-400 font-sans font-medium">Negative Sentiment</td>
                      {data.comparison_products.map((item) => (
                        <td
                          key={item.product_id}
                          className={`p-3 text-rose-400 font-semibold ${
                            item.is_selected ? 'bg-purple-950/20 border-x border-purple-500/20' : ''
                          }`}
                        >
                          {item.negative_percentage}%
                        </td>
                      ))}
                    </tr>

                    {/* Common Pros */}
                    <tr>
                      <td className="p-3 text-slate-400 font-sans font-medium">Common Pros</td>
                      {data.comparison_products.map((item) => (
                        <td
                          key={item.product_id}
                          className={`p-3 font-sans text-xs text-slate-300 ${
                            item.is_selected ? 'bg-purple-950/20 border-x border-purple-500/20' : ''
                          }`}
                        >
                          <div className="space-y-1">
                            {item.common_pros.map((pro, i) => (
                              <div key={i} className="text-emerald-300 text-[11px] flex items-center gap-1">
                                <span>✓</span>
                                <span>{pro}</span>
                              </div>
                            ))}
                          </div>
                        </td>
                      ))}
                    </tr>

                    {/* Common Cons */}
                    <tr>
                      <td className="p-3 text-slate-400 font-sans font-medium">Common Cons</td>
                      {data.comparison_products.map((item) => (
                        <td
                          key={item.product_id}
                          className={`p-3 font-sans text-xs text-slate-300 ${
                            item.is_selected ? 'bg-purple-950/20 border-x border-purple-500/20' : ''
                          }`}
                        >
                          <div className="space-y-1">
                            {item.common_cons.map((con, i) => (
                              <div key={i} className="text-rose-300 text-[11px] flex items-center gap-1">
                                <span>✗</span>
                                <span>{con}</span>
                              </div>
                            ))}
                          </div>
                        </td>
                      ))}
                    </tr>

                    {/* Action / Inspect */}
                    <tr>
                      <td className="p-3 text-slate-400 font-sans font-medium">Explore</td>
                      {data.comparison_products.map((item) => (
                        <td
                          key={item.product_id}
                          className={`p-3 ${item.is_selected ? 'bg-purple-950/20 border-x border-purple-500/20' : ''}`}
                        >
                          {item.is_selected ? (
                            <span className="inline-block rounded-lg bg-purple-500/20 border border-purple-500/40 px-2.5 py-1 text-[11px] font-sans font-bold text-purple-300">
                              Currently Viewing
                            </span>
                          ) : (
                            <button
                              type="button"
                              onClick={() =>
                                onSelectAlternativeProduct &&
                                onSelectAlternativeProduct({
                                  product_id: item.product_id,
                                  product_title: item.product_title,
                                  category: item.category,
                                  review_count: item.review_count,
                                  average_rating: item.average_rating,
                                })
                              }
                              className="inline-flex items-center gap-1 rounded-lg border border-slate-700 bg-slate-800 px-2.5 py-1 text-[11px] font-sans font-medium text-slate-200 hover:bg-purple-600 hover:text-white transition"
                            >
                              <span>Switch to this</span>
                              <ArrowRight className="h-3 w-3" />
                            </button>
                          )}
                        </td>
                      ))}
                    </tr>
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center py-8 px-4 text-center rounded-xl border border-slate-800/80 bg-[#0B0F17]/60">
                <div className="h-10 w-10 rounded-xl bg-purple-950/40 border border-purple-800/30 flex items-center justify-center mb-3 text-purple-400">
                  <BarChart3 className="h-5 w-5" />
                </div>
                <p className="text-sm font-medium text-slate-300">
                  No closely related products found in the dataset.
                </p>
                <p className="text-xs text-slate-500 mt-1 max-w-md">
                  There are no other products in the dataset with matching product type or sub-category metadata for side-by-side comparison.
                </p>
              </div>
            )}
          </div>

          {/* 4. FINAL DECISION PANEL ("MY RECOMMENDATION") */}
          <div className="relative overflow-hidden rounded-2xl border border-gradient border-purple-500/40 bg-gradient-to-br from-[#111827] via-[#0B0F17] to-[#151226] p-6 sm:p-7 backdrop-blur-xl shadow-2xl space-y-5">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-800 pb-4">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-tr from-purple-600 to-cyan-400 p-0.5 shadow-glow-purple">
                  <div className="flex h-full w-full items-center justify-center rounded-[10px] bg-[#0B0F17]">
                    <Award className="h-5 w-5 text-purple-400" />
                  </div>
                </div>
                <div>
                  <h3 className="text-base font-bold text-white uppercase tracking-wider font-mono">
                    YOUR PRODUCT DECISION
                  </h3>
                  <p className="text-[11px] font-mono text-purple-300">
                    Target Criteria: {data.user_priorities.join(' • ')}
                  </p>
                </div>
              </div>

              <span className="rounded-full bg-emerald-500/10 border border-emerald-500/30 px-3 py-1 text-xs font-mono text-emerald-400 font-semibold self-start sm:self-center">
                Top Match Verified
              </span>
            </div>

            {/* Recommendation Box */}
            <div className="rounded-xl border border-purple-500/30 bg-[#0B0F17]/90 p-5 space-y-3">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                <div>
                  <span className="text-[10px] font-mono uppercase tracking-wider text-slate-500">
                    RECOMMENDED MATCH
                  </span>
                  <h4 className="text-lg font-black text-white flex items-center gap-2">
                    <span>{data.recommended_product.product_title}</span>
                    <span className="text-xs font-mono text-amber-400">
                      ({data.recommended_product.average_rating} ★)
                    </span>
                  </h4>
                </div>

                <div className="text-xs font-mono text-slate-400">
                  {data.recommended_product.review_count.toLocaleString()} dataset reviews
                </div>
              </div>

              <p className="text-xs sm:text-sm text-slate-200 leading-relaxed">
                {data.recommendation_headline}
              </p>
            </div>

            {/* Why this matches your requirements */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
              <div className="rounded-xl border border-emerald-500/20 bg-emerald-950/15 p-4 space-y-2">
                <span className="font-bold text-emerald-400 block">
                  Strengths for you:
                </span>
                <ul className="space-y-1.5 text-slate-300">
                  {data.strengths_for_you.map((s, i) => (
                    <li key={i} className="flex items-start gap-2">
                      <span className="text-emerald-400 font-bold">✓</span>
                      <span>{s}</span>
                    </li>
                  ))}
                </ul>
              </div>

              <div className="rounded-xl border border-amber-500/20 bg-amber-950/15 p-4 space-y-2">
                <span className="font-bold text-amber-400 block">
                  Things to consider:
                </span>
                <ul className="space-y-1.5 text-slate-300">
                  {data.things_to_consider.map((t, i) => (
                    <li key={i} className="flex items-start gap-2">
                      <span className="text-amber-400 font-bold">⚠</span>
                      <span>{t}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>

            {/* Footer Transparency Disclaimer */}
            <div className="pt-2 text-[11px] font-mono text-slate-500 flex items-center justify-between border-t border-slate-800/80">
              <span className="flex items-center gap-1.5">
                <ShieldCheck className="h-3.5 w-3.5 text-cyan-400" />
                <span>Source: ReviewIQ Product Review Dataset • Zero fabricated claims</span>
              </span>
              <span className="hidden sm:inline">
                Analyzed for: {data.selected_product.product_title}
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
