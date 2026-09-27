import React, { useState } from 'react';
import { Layers, ThumbsUp, ThumbsDown, ChevronDown, ChevronUp, Quote, ExternalLink } from 'lucide-react';
import { ProConTheme } from '../types/ecommerce';

interface AspectInsightsCardProps {
  pros: ProConTheme[];
  cons: ProConTheme[];
  totalAnalyzedReviews?: number;
  onSelectThemeForEvidence?: (theme: string, sentiment: 'positive' | 'negative') => void;
  selectedTheme?: string | null;
}

interface UnifiedAspect {
  name: string;
  sentiment: 'positive' | 'negative' | 'mixed';
  positiveCount: number;
  negativeCount: number;
  positivePct: number;
  negativePct: number;
  examples: string[];
  evidenceIds: number[];
}

export const AspectInsightsCard: React.FC<AspectInsightsCardProps> = ({
  pros = [],
  cons = [],
  totalAnalyzedReviews = 0,
  onSelectThemeForEvidence,
  selectedTheme,
}) => {
  const [filter, setFilter] = useState<'all' | 'positive' | 'negative'>('all');
  const [expandedAspect, setExpandedAspect] = useState<string | null>(null);

  // Dynamically assemble aspects from backend returned themes - ZERO HARDCODED ASPECTS
  const aspectsMap = new Map<string, UnifiedAspect>();

  pros.forEach((pro) => {
    const key = pro.theme.toLowerCase().trim();
    if (!aspectsMap.has(key)) {
      aspectsMap.set(key, {
        name: pro.theme,
        sentiment: 'positive',
        positiveCount: pro.review_count,
        negativeCount: 0,
        positivePct: pro.percentage,
        negativePct: 0,
        examples: [...pro.example_reviews],
        evidenceIds: [...pro.evidence_review_ids],
      });
    } else {
      const existing = aspectsMap.get(key)!;
      existing.positiveCount += pro.review_count;
      existing.positivePct += pro.percentage;
      existing.examples.push(...pro.example_reviews);
      existing.evidenceIds.push(...pro.evidence_review_ids);
      existing.sentiment = 'mixed';
    }
  });

  cons.forEach((con) => {
    const key = con.theme.toLowerCase().trim();
    if (!aspectsMap.has(key)) {
      aspectsMap.set(key, {
        name: con.theme,
        sentiment: 'negative',
        positiveCount: 0,
        negativeCount: con.review_count,
        positivePct: 0,
        negativePct: con.percentage,
        examples: [...con.example_reviews],
        evidenceIds: [...con.evidence_review_ids],
      });
    } else {
      const existing = aspectsMap.get(key)!;
      existing.negativeCount += con.review_count;
      existing.negativePct += con.percentage;
      existing.examples.push(...con.example_reviews);
      existing.evidenceIds.push(...con.evidence_review_ids);
      existing.sentiment = 'mixed';
    }
  });

  const dynamicAspects = Array.from(aspectsMap.values()).sort(
    (a, b) => b.positiveCount + b.negativeCount - (a.positiveCount + a.negativeCount)
  );

  const filteredAspects = dynamicAspects.filter((aspect) => {
    if (filter === 'positive') return aspect.sentiment === 'positive' || aspect.sentiment === 'mixed';
    if (filter === 'negative') return aspect.sentiment === 'negative' || aspect.sentiment === 'mixed';
    return true;
  });

  const toggleExpand = (name: string) => {
    setExpandedAspect(expandedAspect === name ? null : name);
  };

  return (
    <div className="premium-panel p-6 border border-[#292A2B] bg-[#151617]">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-6">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg border border-[#D4AF5A]/40 bg-[#1E1B15] text-[#D4AF5A]">
            <Layers className="h-4 w-4" />
          </div>
          <div>
            <h3 className="text-sm font-semibold tracking-wide text-[#F5F2EA]">
              Dynamic Aspect Insights
            </h3>
            <p className="text-[11px] text-[#74736E]">
              Extracted specifically for this product from customer discourse
              {totalAnalyzedReviews > 0 && ` (${totalAnalyzedReviews.toLocaleString()} reviews)`}
            </p>
          </div>
        </div>

        {/* Filter Controls */}
        <div className="flex items-center gap-1 rounded-lg border border-[#292A2B] bg-[#121314] p-1 text-xs">
          <button
            onClick={() => setFilter('all')}
            className={`rounded-md px-2.5 py-1 text-[11px] font-medium transition ${
              filter === 'all'
                ? 'bg-[#1C1D1F] text-[#F0D58A] shadow-sm'
                : 'text-[#AAA79F] hover:text-[#F5F2EA]'
            }`}
          >
            All ({dynamicAspects.length})
          </button>
          <button
            onClick={() => setFilter('positive')}
            className={`rounded-md px-2.5 py-1 text-[11px] font-medium transition ${
              filter === 'positive'
                ? 'bg-emerald-950/60 text-emerald-400 border border-emerald-500/30'
                : 'text-[#AAA79F] hover:text-emerald-400'
            }`}
          >
            Pros
          </button>
          <button
            onClick={() => setFilter('negative')}
            className={`rounded-md px-2.5 py-1 text-[11px] font-medium transition ${
              filter === 'negative'
                ? 'bg-rose-950/60 text-rose-400 border border-rose-500/30'
                : 'text-[#AAA79F] hover:text-rose-400'
            }`}
          >
            Cons
          </button>
        </div>
      </div>

      {filteredAspects.length === 0 ? (
        <div className="py-8 text-center text-xs text-[#74736E]">
          No dynamic aspects found matching the selected filter.
        </div>
      ) : (
        <div className="space-y-3">
          {filteredAspects.map((aspect) => {
            const isSelected = selectedTheme === aspect.name;
            const isExpanded = expandedAspect === aspect.name;
            const totalMentions = aspect.positiveCount + aspect.negativeCount;

            return (
              <div
                key={aspect.name}
                className={`rounded-xl border transition-all ${
                  isSelected
                    ? 'border-[#D4AF5A] bg-[#1B1914] shadow-gold-subtle'
                    : 'border-[#292A2B] bg-[#18191B] hover:border-[#383A40]'
                }`}
              >
                <div className="p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex flex-wrap items-center gap-2 mb-1.5">
                      <span className="text-sm font-semibold text-[#F5F2EA]">
                        {aspect.name}
                      </span>

                      {/* Sentiment Badge */}
                      {aspect.sentiment === 'positive' && (
                        <span className="inline-flex items-center gap-1 rounded bg-emerald-950/50 px-2 py-0.5 text-[10px] font-medium text-emerald-400 border border-emerald-500/30">
                          <ThumbsUp className="h-2.5 w-2.5" />
                          Positive ({aspect.positivePct}%)
                        </span>
                      )}
                      {aspect.sentiment === 'negative' && (
                        <span className="inline-flex items-center gap-1 rounded bg-rose-950/50 px-2 py-0.5 text-[10px] font-medium text-rose-400 border border-rose-500/30">
                          <ThumbsDown className="h-2.5 w-2.5" />
                          Negative ({aspect.negativePct}%)
                        </span>
                      )}
                      {aspect.sentiment === 'mixed' && (
                        <span className="inline-flex items-center gap-1 rounded bg-amber-950/50 px-2 py-0.5 text-[10px] font-medium text-amber-400 border border-amber-500/30">
                          Mixed Aspect
                        </span>
                      )}

                      <span className="text-[11px] text-[#74736E] font-mono">
                        {totalMentions} reviews
                      </span>
                    </div>

                    {/* First review example quote */}
                    {aspect.examples.length > 0 && (
                      <p className="line-clamp-1 text-xs text-[#AAA79F] italic flex items-center gap-1">
                        <Quote className="h-3 w-3 text-[#D4AF5A] shrink-0" />
                        "{aspect.examples[0]}"
                      </p>
                    )}
                  </div>

                  {/* Action Buttons */}
                  <div className="flex items-center gap-2 shrink-0">
                    {onSelectThemeForEvidence && (
                      <button
                        onClick={() =>
                          onSelectThemeForEvidence(
                            aspect.name,
                            aspect.sentiment === 'negative' ? 'negative' : 'positive'
                          )
                        }
                        className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition ${
                          isSelected
                            ? 'bg-[#D4AF5A] text-[#121314] font-semibold'
                            : 'border border-[#292A2B] bg-[#141517] text-[#D4AF5A] hover:border-[#D4AF5A]/50 hover:bg-[#1E1B15]'
                        }`}
                      >
                        <ExternalLink className="h-3 w-3" />
                        {isSelected ? 'Viewing Evidence' : 'Inspect Evidence'}
                      </button>
                    )}

                    {aspect.examples.length > 1 && (
                      <button
                        onClick={() => toggleExpand(aspect.name)}
                        className="rounded-lg border border-[#292A2B] bg-[#141517] p-1.5 text-[#AAA79F] hover:text-[#F5F2EA] transition"
                        title={isExpanded ? 'Collapse quotes' : 'Expand quotes'}
                      >
                        {isExpanded ? (
                          <ChevronUp className="h-3.5 w-3.5" />
                        ) : (
                          <ChevronDown className="h-3.5 w-3.5" />
                        )}
                      </button>
                    )}
                  </div>
                </div>

                {/* Expanded quotes accordion */}
                {isExpanded && aspect.examples.length > 1 && (
                  <div className="border-t border-[#242526] bg-[#131416] p-4 space-y-2 rounded-b-xl">
                    <p className="text-[11px] font-semibold uppercase tracking-wider text-[#D4AF5A]">
                      Additional Customer Quotations ({aspect.examples.length})
                    </p>
                    {aspect.examples.slice(1).map((ex, i) => (
                      <div
                        key={i}
                        className="rounded-md border border-[#292A2B] bg-[#18191B] p-2.5 text-xs text-[#AAA79F] italic"
                      >
                        "{ex}"
                      </div>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
