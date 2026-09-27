import React from 'react';
import {
  Sparkles,
  Layers,
  ShieldCheck,
  BarChart3,
  MessageSquare,
  ArrowRight,
  Database,
  Cpu,
} from 'lucide-react';
import { HeroSearch } from '../components/HeroSearch';
import { ProductSummary } from '../types/ecommerce';
import { getProductHistory } from '../services/historyStorage';

interface HomePageProps {
  onSelectProduct: (product: ProductSummary) => void;
  onNavigateToAnalyzer: () => void;
  onNavigateToSearch?: () => void;
}

export const HomePage: React.FC<HomePageProps> = ({
  onSelectProduct,
  onNavigateToAnalyzer,
}) => {
  const recentHistory = getProductHistory();

  return (
    <div className="space-y-16 pb-20">
      {/* Hero Section */}
      <section className="relative pt-12 sm:pt-20 px-4 sm:px-6 lg:px-8 text-center max-w-5xl mx-auto">
        {/* Subtle Gold Tagline */}
        <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-[#D4AF5A]/30 bg-[#1A1815] px-4 py-1.5 shadow-sm">
          <Sparkles className="h-3.5 w-3.5 text-[#D4AF5A]" />
          <span className="text-xs font-semibold uppercase tracking-[0.2em] text-[#F0D58A]">
            Enterprise Product Intelligence
          </span>
        </div>

        {/* Hero Title */}
        <h1 className="text-3xl sm:text-5xl lg:text-6xl font-medium tracking-tight text-[#F5F2EA] leading-[1.12]">
          Turn customer reviews into{' '}
          <span className="text-transparent bg-clip-text bg-gradient-to-r from-[#F0D58A] via-[#D4AF5A] to-[#B89445]">
            product intelligence.
          </span>
        </h1>

        {/* Subtitle */}
        <p className="mt-5 max-w-2xl mx-auto text-sm sm:text-base text-[#AAA79F] leading-relaxed">
          ReviewIQ synthesizes millions of authentic customer reviews into structured
          aspect insights, verified pros & cons, and traceable evidence citations with zero hallucination.
        </p>

        {/* Search Bar Container */}
        <div className="mt-10">
          <HeroSearch onSelectProduct={onSelectProduct} />
        </div>
      </section>

      {/* Recently Analyzed Products (if any) */}
      {recentHistory.length > 0 && (
        <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="mb-4 flex items-center justify-between">
            <h3 className="text-xs font-semibold uppercase tracking-[0.18em] text-[#AAA79F]">
              Recently Analyzed Products
            </h3>
            <span className="text-[11px] text-[#74736E]">Cached locally</span>
          </div>

          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {recentHistory.slice(0, 4).map((item) => (
              <button
                key={item.productId}
                onClick={() =>
                  onSelectProduct({
                    product_id: item.productId,
                    product_title: item.productTitle,
                    category: item.category,
                    review_count: item.reviewCount,
                    average_rating: item.overallRating,
                  })
                }
                className="premium-panel premium-panel-hover p-4 text-left border border-[#292A2B] bg-[#141517] group"
              >
                <div className="mb-2 flex items-center justify-between">
                  <span className="text-[10px] text-[#74736E] font-mono">
                    {item.productId}
                  </span>
                  <span className="text-xs font-semibold text-[#F0D58A]">
                    ★ {item.overallRating.toFixed(1)}
                  </span>
                </div>
                <h4 className="line-clamp-1 text-xs font-semibold text-[#F5F2EA] group-hover:text-[#F0D58A] transition-colors">
                  {item.productTitle}
                </h4>
                <p className="mt-1 text-[11px] text-[#74736E]">
                  {item.reviewCount.toLocaleString()} reviews
                </p>
              </button>
            ))}
          </div>
        </section>
      )}

      {/* How ReviewIQ Works */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="mb-10 text-center max-w-xl mx-auto">
          <div className="mb-2 inline-flex items-center gap-1.5 text-xs font-semibold uppercase tracking-[0.2em] text-[#D4AF5A]">
            <span>Architecture</span>
          </div>
          <h2 className="text-2xl sm:text-3xl font-medium tracking-tight text-[#F5F2EA]">
            How ReviewIQ Generates Intelligence
          </h2>
          <p className="mt-2 text-xs sm:text-sm text-[#AAA79F]">
            Deterministic data pipelines paired with grounded AI reasoning
          </p>
        </div>

        <div className="grid gap-6 md:grid-cols-3">
          {/* Step 1 */}
          <div className="premium-panel p-6 border border-[#292A2B] bg-[#141517] relative">
            <div className="mb-4 flex h-10 w-10 items-center justify-center rounded-lg border border-[#D4AF5A]/30 bg-[#1D1B16] text-[#D4AF5A]">
              <Database className="h-5 w-5" />
            </div>
            <span className="text-[10px] font-mono font-semibold uppercase text-[#D4AF5A]">
              Phase 01
            </span>
            <h3 className="mt-1 text-base font-semibold text-[#F5F2EA]">
              Ingest & Index 4M Reviews
            </h3>
            <p className="mt-2 text-xs text-[#AAA79F] leading-relaxed">
              Real Amazon e-commerce customer reviews are indexed with priority ranking,
              sentiment categorization, and verified rating distribution.
            </p>
          </div>

          {/* Step 2 */}
          <div className="premium-panel p-6 border border-[#292A2B] bg-[#141517] relative">
            <div className="mb-4 flex h-10 w-10 items-center justify-center rounded-lg border border-[#D4AF5A]/30 bg-[#1D1B16] text-[#D4AF5A]">
              <Cpu className="h-5 w-5" />
            </div>
            <span className="text-[10px] font-mono font-semibold uppercase text-[#D4AF5A]">
              Phase 02
            </span>
            <h3 className="mt-1 text-base font-semibold text-[#F5F2EA]">
              Dynamic Aspect Mining
            </h3>
            <p className="mt-2 text-xs text-[#AAA79F] leading-relaxed">
              Aspects are mined dynamically per product without fixed presets. Sentiment weights
              and mention percentages quantify customer consensus.
            </p>
          </div>

          {/* Step 3 */}
          <div className="premium-panel p-6 border border-[#292A2B] bg-[#141517] relative">
            <div className="mb-4 flex h-10 w-10 items-center justify-center rounded-lg border border-[#D4AF5A]/30 bg-[#1D1B16] text-[#D4AF5A]">
              <ShieldCheck className="h-5 w-5" />
            </div>
            <span className="text-[10px] font-mono font-semibold uppercase text-[#D4AF5A]">
              Phase 03
            </span>
            <h3 className="mt-1 text-base font-semibold text-[#F5F2EA]">
              Traceable Evidence Citations
            </h3>
            <p className="mt-2 text-xs text-[#AAA79F] leading-relaxed">
              Every pro, con, and aspect insight is strictly traceable back to unmodified
              review quotations in the dataset with zero synthetic invention.
            </p>
          </div>
        </div>
      </section>

      {/* Key Capabilities */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="premium-panel p-8 sm:p-10 border border-[#292A2B] bg-[#131416]">
          <div className="max-w-2xl mb-8">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[#D4AF5A] mb-2">
              Platform Features
            </p>
            <h2 className="text-2xl sm:text-3xl font-medium tracking-tight text-[#F5F2EA]">
              Built for Serious Product Intelligence
            </h2>
            <p className="mt-2 text-xs sm:text-sm text-[#AAA79F]">
              ReviewIQ provides high information density and verifiable clarity for product managers,
              market researchers, and enterprise buyers.
            </p>
          </div>

          <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
            <div className="rounded-xl border border-[#292A2B] bg-[#17181A] p-5">
              <Layers className="h-5 w-5 text-[#D4AF5A] mb-3" />
              <h4 className="text-sm font-semibold text-[#F5F2EA]">Dynamic Aspects</h4>
              <p className="mt-1.5 text-xs text-[#AAA79F] leading-relaxed">
                No rigid categories. Automatically adapts whether analyzing coffee makers or noise-cancelling headphones.
              </p>
            </div>

            <div className="rounded-xl border border-[#292A2B] bg-[#17181A] p-5">
              <ShieldCheck className="h-5 w-5 text-emerald-400 mb-3" />
              <h4 className="text-sm font-semibold text-[#F5F2EA]">Zero Hallucination</h4>
              <p className="mt-1.5 text-xs text-[#AAA79F] leading-relaxed">
                Constrained Gemini AI synthesis strictly grounded in retrieved review records.
              </p>
            </div>

            <div className="rounded-xl border border-[#292A2B] bg-[#17181A] p-5">
              <BarChart3 className="h-5 w-5 text-[#F0D58A] mb-3" />
              <h4 className="text-sm font-semibold text-[#F5F2EA]">Statistical Confidence</h4>
              <p className="mt-1.5 text-xs text-[#AAA79F] leading-relaxed">
                Review volume counts, sentiment percentages, and rating histograms compute true distribution.
              </p>
            </div>

            <div className="rounded-xl border border-[#292A2B] bg-[#17181A] p-5">
              <MessageSquare className="h-5 w-5 text-rose-400 mb-3" />
              <h4 className="text-sm font-semibold text-[#F5F2EA]">Ad-Hoc Review Pipeline</h4>
              <p className="mt-1.5 text-xs text-[#AAA79F] leading-relaxed">
                Analyze single custom customer reviews in real time using LangGraph orchestration.
              </p>
            </div>
          </div>

          {/* Quick CTA banner */}
          <div className="mt-10 pt-6 border-t border-[#242526] flex flex-col sm:flex-row items-center justify-between gap-4">
            <span className="text-xs text-[#AAA79F]">
              Have an individual review to analyze? Use the LangGraph review analyzer.
            </span>
            <button
              onClick={onNavigateToAnalyzer}
              className="gold-button inline-flex items-center gap-2 px-5 py-2 text-xs font-semibold"
            >
              Open Single Review Analyzer
              <ArrowRight className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
      </section>
    </div>
  );
};
