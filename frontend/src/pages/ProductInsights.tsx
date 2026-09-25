import React from 'react';
import { Search, Star, BarChart3, MessageSquare, ArrowLeft } from 'lucide-react';

interface ProductInsightsProps {
  onBack?: () => void;
}

export const ProductInsights: React.FC<ProductInsightsProps> = ({ onBack }) => {
  return (
    <div className="min-h-screen bg-[var(--bg-main)] text-[var(--text-primary)]">
      {/* Header */}
      <header className="border-b border-[var(--border)] bg-[var(--bg-surface)]">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-5">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.22em] gold-text">
              ReviewIQ
            </p>
            <h1 className="mt-1 text-2xl font-semibold">
              Product Insights
            </h1>
          </div>

          {onBack && (
            <button
              onClick={onBack}
              className="flex items-center gap-2 rounded-lg border border-[var(--border)] px-4 py-2 text-sm text-[var(--text-secondary)] transition hover:border-[var(--border-gold)] hover:text-[var(--text-primary)]"
            >
              <ArrowLeft size={16} />
              Back
            </button>
          )}
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-6 py-10">
        {/* Search */}
        <section className="premium-panel p-6">
          <div className="mb-5">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] gold-text">
              Product Intelligence
            </p>
            <h2 className="mt-2 text-2xl font-semibold">
              Search a product
            </h2>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-[var(--text-secondary)]">
              Search for a product to explore customer reviews, ratings,
              sentiment and aspect-level insights.
            </p>
          </div>

          <div className="flex flex-col gap-3 sm:flex-row">
            <div className="flex flex-1 items-center gap-3 rounded-lg border border-[var(--border)] bg-[var(--bg-elevated)] px-4 py-3">
              <Search size={18} className="text-[var(--text-muted)]" />
              <input
                type="text"
                placeholder="Enter product name..."
                className="w-full bg-transparent text-sm text-[var(--text-primary)] placeholder:text-[var(--text-muted)]"
              />
            </div>

            <button className="gold-button px-6 py-3 text-sm">
              Analyze Product
            </button>
          </div>
        </section>

        {/* Empty state */}
        <section className="mt-8 grid gap-5 md:grid-cols-3">
          <InsightCard
            icon={<Star size={20} />}
            title="Overall Rating"
            description="Product rating will appear here after analysis."
          />

          <InsightCard
            icon={<BarChart3 size={20} />}
            title="Aspect Insights"
            description="Relevant product aspects and their ratings will appear here."
          />

          <InsightCard
            icon={<MessageSquare size={20} />}
            title="Customer Reviews"
            description="Customer review intelligence will appear here."
          />
        </section>

        {/* Analysis area */}
        <section className="mt-8 premium-panel p-8">
          <div className="flex min-h-[280px] flex-col items-center justify-center text-center">
            <div className="mb-5 flex h-14 w-14 items-center justify-center rounded-full border border-[var(--border-gold)] bg-[var(--bg-elevated)] gold-text">
              <BarChart3 size={24} />
            </div>

            <h3 className="text-xl font-semibold">
              Product analysis will appear here
            </h3>

            <p className="mt-3 max-w-xl text-sm leading-6 text-[var(--text-secondary)]">
              Once a product is selected, ReviewIQ will display review
              intelligence, sentiment, aspect-level ratings and customer
              feedback.
            </p>
          </div>
        </section>
      </main>
    </div>
  );
};

interface InsightCardProps {
  icon: React.ReactNode;
  title: string;
  description: string;
}

const InsightCard: React.FC<InsightCardProps> = ({
  icon,
  title,
  description,
}) => {
  return (
    <div className="premium-panel premium-panel-hover p-6">
      <div className="mb-4 flex h-10 w-10 items-center justify-center rounded-lg border border-[var(--border-gold)] gold-text">
        {icon}
      </div>

      <h3 className="font-semibold">{title}</h3>

      <p className="mt-2 text-sm leading-6 text-[var(--text-secondary)]">
        {description}
      </p>
    </div>
  );
};