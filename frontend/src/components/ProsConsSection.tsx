import React from 'react';
import { ThumbsUp, ThumbsDown, CheckCircle2, AlertOctagon, ShieldCheck, ChevronRight } from 'lucide-react';
import { ProConTheme } from '../types/ecommerce';

interface ProsConsSectionProps {
  pros: ProConTheme[];
  cons: ProConTheme[];
  authenticitySignals?: string[];
  onSelectTheme?: (theme: string, sentiment: 'positive' | 'negative') => void;
  selectedTheme?: string | null;
}

export const ProsConsSection: React.FC<ProsConsSectionProps> = ({
  pros = [],
  cons = [],
  authenticitySignals = [],
  onSelectTheme,
  selectedTheme,
}) => {
  return (
    <div className="space-y-4">
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Pros Column */}
        <div className="premium-panel p-6 border border-[#292A2B] bg-[#151617]">
          <div className="mb-5 flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg border border-emerald-500/30 bg-emerald-950/30 text-emerald-400">
                <ThumbsUp className="h-4 w-4" />
              </div>
              <div>
                <h3 className="text-sm font-semibold text-[#F5F2EA]">Quantified Strengths (Pros)</h3>
                <p className="text-[11px] text-[#74736E]">Supported by positive customer feedback</p>
              </div>
            </div>
            <span className="rounded bg-emerald-950/40 px-2 py-0.5 text-xs font-semibold text-emerald-400 border border-emerald-500/20">
              {pros.length} Identified
            </span>
          </div>

          {pros.length === 0 ? (
            <p className="py-6 text-center text-xs text-[#74736E] italic">
              No distinct pro themes recorded for this product.
            </p>
          ) : (
            <div className="space-y-3">
              {pros.map((pro) => {
                const isSelected = selectedTheme === pro.theme;
                return (
                  <div
                    key={pro.theme}
                    onClick={() => onSelectTheme && onSelectTheme(pro.theme, 'positive')}
                    className={`rounded-xl border p-4 transition-all cursor-pointer ${
                      isSelected
                        ? 'border-emerald-500/70 bg-emerald-950/20 shadow-sm'
                        : 'border-[#292A2B] bg-[#18191B] hover:border-emerald-500/40 hover:bg-[#1A1C1E]'
                    }`}
                  >
                    <div className="flex items-center justify-between gap-3 mb-2">
                      <div className="flex items-center gap-2">
                        <CheckCircle2 className="h-4 w-4 text-emerald-400 shrink-0" />
                        <span className="text-sm font-semibold text-[#F5F2EA]">
                          {pro.theme}
                        </span>
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        <span className="rounded bg-emerald-950/60 px-2 py-0.5 text-xs font-mono font-medium text-emerald-300 border border-emerald-500/30">
                          {pro.percentage}%
                        </span>
                        <span className="text-[11px] text-[#74736E]">
                          ({pro.review_count} revs)
                        </span>
                      </div>
                    </div>

                    {pro.example_reviews && pro.example_reviews.length > 0 && (
                      <p className="text-xs text-[#AAA79F] leading-relaxed italic line-clamp-2 mt-1.5 pl-6 border-l-2 border-emerald-500/30">
                        "{pro.example_reviews[0]}"
                      </p>
                    )}

                    {onSelectTheme && (
                      <div className="mt-3 flex items-center justify-end text-[11px] font-medium text-emerald-400 gap-1">
                        <span>Inspect {pro.review_count} supporting reviews</span>
                        <ChevronRight className="h-3 w-3" />
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Cons Column */}
        <div className="premium-panel p-6 border border-[#292A2B] bg-[#151617]">
          <div className="mb-5 flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg border border-rose-500/30 bg-rose-950/30 text-rose-400">
                <ThumbsDown className="h-4 w-4" />
              </div>
              <div>
                <h3 className="text-sm font-semibold text-[#F5F2EA]">Customer Pain Points (Cons)</h3>
                <p className="text-[11px] text-[#74736E]">Reported issues and common complaints</p>
              </div>
            </div>
            <span className="rounded bg-rose-950/40 px-2 py-0.5 text-xs font-semibold text-rose-400 border border-rose-500/20">
              {cons.length} Identified
            </span>
          </div>

          {cons.length === 0 ? (
            <p className="py-6 text-center text-xs text-[#74736E] italic">
              No significant customer complaints identified.
            </p>
          ) : (
            <div className="space-y-3">
              {cons.map((con) => {
                const isSelected = selectedTheme === con.theme;
                return (
                  <div
                    key={con.theme}
                    onClick={() => onSelectTheme && onSelectTheme(con.theme, 'negative')}
                    className={`rounded-xl border p-4 transition-all cursor-pointer ${
                      isSelected
                        ? 'border-rose-500/70 bg-rose-950/20 shadow-sm'
                        : 'border-[#292A2B] bg-[#18191B] hover:border-rose-500/40 hover:bg-[#1A1C1E]'
                    }`}
                  >
                    <div className="flex items-center justify-between gap-3 mb-2">
                      <div className="flex items-center gap-2">
                        <AlertOctagon className="h-4 w-4 text-rose-400 shrink-0" />
                        <span className="text-sm font-semibold text-[#F5F2EA]">
                          {con.theme}
                        </span>
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        <span className="rounded bg-rose-950/60 px-2 py-0.5 text-xs font-mono font-medium text-rose-300 border border-rose-500/30">
                          {con.percentage}%
                        </span>
                        <span className="text-[11px] text-[#74736E]">
                          ({con.review_count} revs)
                        </span>
                      </div>
                    </div>

                    {con.example_reviews && con.example_reviews.length > 0 && (
                      <p className="text-xs text-[#AAA79F] leading-relaxed italic line-clamp-2 mt-1.5 pl-6 border-l-2 border-rose-500/30">
                        "{con.example_reviews[0]}"
                      </p>
                    )}

                    {onSelectTheme && (
                      <div className="mt-3 flex items-center justify-end text-[11px] font-medium text-rose-400 gap-1">
                        <span>Inspect {con.review_count} supporting reviews</span>
                        <ChevronRight className="h-3 w-3" />
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* Authenticity Signals Banner */}
      {authenticitySignals.length > 0 && (
        <div className="rounded-xl border border-[#292A2B] bg-[#141517] p-4 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2 text-xs text-[#AAA79F]">
            <ShieldCheck className="h-4 w-4 text-[#D4AF5A]" />
            <span className="font-semibold text-[#F5F2EA]">Authenticity Verification:</span>
            <span>{authenticitySignals.join(' • ')}</span>
          </div>
          <span className="text-[10px] text-[#74736E] uppercase tracking-wider">
            Deterministic Sentiment Scoring
          </span>
        </div>
      )}
    </div>
  );
};
