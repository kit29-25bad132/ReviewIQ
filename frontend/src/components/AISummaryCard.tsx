import React from 'react';
import { Sparkles, ShieldCheck, Tag, Loader2 } from 'lucide-react';
import { AISummaryResponse } from '../types/ecommerce';

interface AISummaryCardProps {
  summaryData: AISummaryResponse | null;
  fallbackSummary?: string;
  isLoading?: boolean;
}

export const AISummaryCard: React.FC<AISummaryCardProps> = ({
  summaryData,
  fallbackSummary,
  isLoading = false,
}) => {
  const summaryText = summaryData?.summary || fallbackSummary;
  const keyThemes = summaryData?.key_themes || [];
  const sourceLabel =
    summaryData?.source_label || 'Synthesized strictly from authentic dataset reviews';

  return (
    <div className="premium-panel p-6 sm:p-7 border border-[#292A2B] bg-[#141517] relative overflow-hidden">
      {/* Subtle gold line accent */}
      <div className="absolute top-0 left-0 right-0 h-[2px] bg-gradient-to-r from-transparent via-[#D4AF5A]/60 to-transparent" />

      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg border border-[#D4AF5A]/40 bg-[#1E1B15] text-[#D4AF5A]">
            <Sparkles className="h-4 w-4" />
          </div>
          <div>
            <h3 className="text-sm font-semibold tracking-wide text-[#F5F2EA] uppercase">
              AI Executive Summary
            </h3>
            <p className="text-[11px] text-[#74736E]">
              Zero-hallucination synthesis of customer feedback
            </p>
          </div>
        </div>

        <div className="flex items-center gap-1.5 rounded-full border border-[#292A2B] bg-[#17181A] px-3 py-1 text-[11px] text-[#AAA79F]">
          <ShieldCheck className="h-3.5 w-3.5 text-[#D4AF5A]" />
          <span>{sourceLabel}</span>
        </div>
      </div>

      {isLoading ? (
        <div className="py-6 flex flex-col items-center justify-center text-center space-y-2">
          <Loader2 className="h-5 w-5 animate-spin text-[#D4AF5A]" />
          <p className="text-xs text-[#AAA79F]">Generating grounded AI summary from reviews...</p>
        </div>
      ) : summaryText ? (
        <div>
          <p className="text-sm sm:text-base leading-relaxed text-[#F5F2EA] font-normal">
            {summaryText}
          </p>

          {/* Dynamic Key Themes from the AI analysis */}
          {keyThemes.length > 0 && (
            <div className="mt-5 pt-4 border-t border-[#242526] flex flex-wrap items-center gap-2">
              <span className="text-xs text-[#74736E] font-medium mr-1 flex items-center gap-1">
                <Tag className="h-3 w-3" />
                Key Themes:
              </span>
              {keyThemes.map((theme, idx) => (
                <span
                  key={idx}
                  className="rounded-md border border-[#2B2C30] bg-[#1A1B1E] px-2.5 py-1 text-xs text-[#AAA79F] hover:border-[#D4AF5A]/30 hover:text-[#F0D58A] transition-colors"
                >
                  {theme}
                </span>
              ))}
            </div>
          )}
        </div>
      ) : (
        <div className="py-4 text-xs text-[#74736E] italic">
          No AI summary available for this product yet.
        </div>
      )}
    </div>
  );
};
