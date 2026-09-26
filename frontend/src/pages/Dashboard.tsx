import React from 'react';
import {
  ArrowRight,
  BarChart3,
  CheckCircle2,
  FileSearch,
  Search,
  Sparkles,
  TrendingUp,
} from 'lucide-react';
import type { Page } from '../App';

interface DashboardProps {
  onNavigate: (page: Page) => void;
}

const features = [
  {
    icon: FileSearch,
    title: 'Review Analysis',
    description:
      'Turn customer reviews into structured product intelligence.',
  },
  {
    icon: TrendingUp,
    title: 'Sentiment & Trends',
    description:
      'Identify recurring opinions, patterns, and emerging issues.',
  },
  {
    icon: BarChart3,
    title: 'Product Insights',
    description:
      'Understand the aspects customers care about most.',
  },
];

export const Dashboard: React.FC<DashboardProps> = ({ onNavigate }) => {
  return (
    <div className="min-h-screen bg-[#0E0F10] text-[#F5F2EA]">

      {/* Navigation */}
      <header className="sticky top-0 z-50 border-b border-[#292A2B]/80 bg-[#0E0F10]/95 backdrop-blur">
        <div className="mx-auto flex h-[74px] max-w-[1280px] items-center justify-between px-6 sm:px-8 lg:px-10">

          {/* Logo */}
          <button
            onClick={() => onNavigate('dashboard')}
            className="flex items-center gap-3"
          >
            <div className="flex h-9 w-9 items-center justify-center rounded-lg border border-[#D4AF5A]/40 bg-[#191714]">
              <Sparkles className="h-4 w-4 text-[#D4AF5A]" />
            </div>

            <div className="text-left">
              <p className="text-[15px] font-semibold tracking-[0.18em]">
                REVIEW<span className="text-[#D4AF5A]">IQ</span>
              </p>
              <p className="text-[8px] uppercase tracking-[0.2em] text-[#74736E]">
                Product Intelligence
              </p>
            </div>
          </button>

          {/* Navigation */}
          <nav className="hidden items-center gap-8 md:flex">
            <button
              onClick={() => onNavigate('dashboard')}
              className="text-xs text-[#F0D58A]"
            >
              Home
            </button>

            <button
              onClick={() => onNavigate('analyze')}
              className="text-xs text-[#92908A] transition hover:text-[#F5F2EA]"
            >
              Analyze
            </button>

            <button
              onClick={() => onNavigate('history')}
              className="text-xs text-[#92908A] transition hover:text-[#F5F2EA]"
            >
              History
            </button>

            <button
              onClick={() => onNavigate('insights')}
              className="text-xs text-[#92908A] transition hover:text-[#F5F2EA]"
            >
              Insights
            </button>
          </nav>

          {/* CTA */}
          <button
            onClick={() => onNavigate('analyze')}
            className="gold-button inline-flex items-center gap-2 px-4 py-2 text-xs"
          >
            Get Started
            <ArrowRight className="h-3.5 w-3.5" />
          </button>
        </div>
      </header>

      <main>

        {/* Hero */}
        <section className="relative overflow-hidden">
          <div className="mx-auto max-w-[1280px] px-6 pb-20 pt-20 sm:px-8 sm:pt-28 lg:px-10 lg:pb-28 lg:pt-32">

            <div className="grid items-center gap-14 lg:grid-cols-[1.05fr_0.95fr]">

              {/* Hero content */}
              <div>

                <div className="mb-7 flex items-center gap-3">
                  <span className="h-px w-8 bg-[#D4AF5A]" />

                  <span className="text-[10px] font-semibold uppercase tracking-[0.25em] text-[#D4AF5A]">
                    AI Product Intelligence
                  </span>
                </div>

                <h1 className="max-w-3xl text-5xl font-medium leading-[1.05] tracking-[-0.045em] sm:text-6xl lg:text-[70px]">
                  Turn customer
                  <br />
                  reviews into
                  <br />
                  <span className="text-[#D4AF5A]">
                    intelligence.
                  </span>
                </h1>

                <p className="mt-7 max-w-xl text-sm leading-7 text-[#8B8982] sm:text-base">
                  ReviewIQ helps you understand what customers really think
                  about a product by transforming reviews into clear,
                  structured insights.
                </p>

                <div className="mt-9 flex flex-col gap-3 sm:flex-row">
                  <button
                    onClick={() => onNavigate('analyze')}
                    className="gold-button inline-flex items-center justify-center gap-2 px-6 py-3.5 text-sm"
                  >
                    <Search className="h-4 w-4" />
                    Analyze a Product
                    <ArrowRight className="h-4 w-4" />
                  </button>

                  <button
                    onClick={() => onNavigate('insights')}
                    className="inline-flex items-center justify-center gap-2 rounded-[9px] border border-[#292A2B] bg-[#151617] px-6 py-3.5 text-sm text-[#AAA79F] transition hover:border-[#D4AF5A]/30 hover:text-[#F5F2EA]"
                  >
                    Explore Insights
                  </button>
                </div>

              </div>

              {/* Intelligence preview */}
              <div className="relative">
                <div className="premium-panel relative overflow-hidden p-6 sm:p-8">

                  <div className="absolute right-0 top-0 h-32 w-32 rounded-bl-full border-b border-l border-[#D4AF5A]/10" />

                  <div className="relative">

                    <div className="flex items-center justify-between border-b border-[#292A2B] pb-5">
                      <div>
                        <p className="text-[10px] uppercase tracking-[0.18em] text-[#74736E]">
                          Product analysis
                        </p>

                        <p className="mt-2 text-sm font-medium text-[#F5F2EA]">
                          Customer Intelligence
                        </p>
                      </div>

                      <span className="rounded-full border border-[#D4AF5A]/20 bg-[#1B1915] px-2.5 py-1 text-[9px] uppercase tracking-[0.12em] text-[#D4AF5A]">
                        AI analyzed
                      </span>
                    </div>

                    <div className="py-7">
                      <p className="text-xs text-[#74736E]">
                        Overall rating
                      </p>

                      <div className="mt-2 flex items-end gap-3">
                        <span className="text-4xl font-medium text-[#F5F2EA]">
                          4.5
                        </span>

                        <span className="mb-1 text-xs text-[#D4AF5A]">
                          / 5
                        </span>
                      </div>
                    </div>

                    <div className="space-y-3 border-t border-[#292A2B] pt-5">

                      {[
                        ['Sound Quality', '4.7', 'Positive'],
                        ['Battery', '3.8', 'Mixed'],
                        ['Comfort', '4.6', 'Positive'],
                        ['Build Quality', '4.5', 'Positive'],
                      ].map(([name, rating, sentiment]) => (
                        <div
                          key={name}
                          className="flex items-center justify-between"
                        >
                          <span className="text-xs text-[#AAA79F]">
                            {name}
                          </span>

                          <div className="flex items-center gap-3">
                            <span className="text-xs text-[#F5F2EA]">
                              {rating}
                            </span>

                            <span className="text-[9px] text-[#A9A17D]">
                              {sentiment}
                            </span>
                          </div>
                        </div>
                      ))}

                    </div>

                  </div>
                </div>

                <div className="absolute -bottom-5 -left-5 hidden rounded-lg border border-[#292A2B] bg-[#151617] px-4 py-3 shadow-2xl sm:block">
                  <p className="text-[9px] uppercase tracking-[0.15em] text-[#74736E]">
                    Reviews analyzed
                  </p>
                  <p className="mt-1 text-lg font-medium text-[#F5F2EA]">
                    156
                  </p>
                </div>
              </div>

            </div>
          </div>
        </section>

        {/* Divider */}
        <div className="mx-auto max-w-[1280px] px-6 sm:px-8 lg:px-10">
          <div className="gold-divider" />
        </div>

        {/* How it works */}
        <section className="mx-auto max-w-[1280px] px-6 py-20 sm:px-8 lg:px-10 lg:py-24">

          <div className="max-w-2xl">
            <p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-[#D4AF5A]">
              How ReviewIQ works
            </p>

            <h2 className="mt-4 text-3xl font-medium tracking-[-0.03em] sm:text-4xl">
              From reviews to
              <span className="text-[#AAA79F]"> useful insight.</span>
            </h2>
          </div>

          <div className="mt-12 grid gap-0 border-y border-[#292A2B] md:grid-cols-3">

            {[
              {
                number: '01',
                title: 'Search a product',
                text: 'Find a product from the available review dataset.',
              },
              {
                number: '02',
                title: 'Analyze reviews',
                text: 'ReviewIQ processes customer feedback and identifies meaningful patterns.',
              },
              {
                number: '03',
                title: 'Discover insights',
                text: 'Explore ratings, sentiment, aspects, pros, cons, and customer reviews.',
              },
            ].map((item, index) => (
              <div
                key={item.number}
                className={`px-6 py-8 sm:px-8 md:py-10 ${
                  index !== 2
                    ? 'border-b border-[#292A2B] md:border-b-0 md:border-r'
                    : ''
                }`}
              >
                <span className="text-[10px] tracking-[0.18em] text-[#D4AF5A]">
                  {item.number}
                </span>

                <h3 className="mt-7 text-lg font-medium text-[#F5F2EA]">
                  {item.title}
                </h3>

                <p className="mt-3 text-sm leading-6 text-[#74736E]">
                  {item.text}
                </p>
              </div>
            ))}

          </div>
        </section>

        {/* Capabilities */}
        <section className="border-y border-[#292A2B] bg-[#111213]">

          <div className="mx-auto max-w-[1280px] px-6 py-20 sm:px-8 lg:px-10 lg:py-24">

            <div className="max-w-2xl">
              <p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-[#D4AF5A]">
                Built for product understanding
              </p>

              <h2 className="mt-4 text-3xl font-medium tracking-[-0.03em] sm:text-4xl">
                See beyond the
                <span className="text-[#AAA79F]"> star rating.</span>
              </h2>
            </div>

            <div className="mt-12 grid gap-4 md:grid-cols-3">

              {features.map((feature) => {
                const Icon = feature.icon;

                return (
                  <div
                    key={feature.title}
                    className="premium-panel premium-panel-hover p-7"
                  >
                    <div className="flex h-10 w-10 items-center justify-center rounded-lg border border-[#D4AF5A]/20 bg-[#1B1915]">
                      <Icon className="h-[18px] w-[18px] text-[#D4AF5A]" />
                    </div>

                    <h3 className="mt-7 text-base font-medium text-[#F5F2EA]">
                      {feature.title}
                    </h3>

                    <p className="mt-3 text-sm leading-6 text-[#74736E]">
                      {feature.description}
                    </p>
                  </div>
                );
              })}

            </div>
          </div>
        </section>

        {/* CTA */}
        <section className="mx-auto max-w-[1280px] px-6 py-20 text-center sm:px-8 lg:px-10 lg:py-28">

          <CheckCircle2 className="mx-auto h-7 w-7 text-[#D4AF5A]" />

          <p className="mt-6 text-[10px] font-semibold uppercase tracking-[0.22em] text-[#D4AF5A]">
            Start exploring
          </p>

          <h2 className="mx-auto mt-4 max-w-2xl text-3xl font-medium tracking-[-0.035em] sm:text-5xl">
            Understand the voice
            <br />
            <span className="text-[#AAA79F]">
              behind every review.
            </span>
          </h2>

          <p className="mx-auto mt-5 max-w-lg text-sm leading-6 text-[#74736E]">
            Search for a product and discover what its customers are really
            saying.
          </p>

          <button
            onClick={() => onNavigate('analyze')}
            className="gold-button mt-8 inline-flex items-center gap-2 px-6 py-3.5 text-sm"
          >
            Analyze a Product
            <ArrowRight className="h-4 w-4" />
          </button>

        </section>

      </main>

      {/* Footer */}
      <footer className="border-t border-[#292A2B]">

        <div className="mx-auto flex max-w-[1280px] flex-col justify-between gap-5 px-6 py-7 sm:px-8 md:flex-row lg:px-10">

          <div>
            <p className="text-[12px] font-semibold tracking-[0.16em]">
              REVIEW<span className="text-[#D4AF5A]">IQ</span>
            </p>

            <p className="mt-1 text-[10px] text-[#555550]">
              Product Review Intelligence Platform
            </p>
          </div>

          <div className="flex flex-wrap gap-5 text-[10px] uppercase tracking-[0.12em] text-[#555550]">
            <button
              onClick={() => onNavigate('analyze')}
              className="transition hover:text-[#D4AF5A]"
            >
              Analyze
            </button>

            <button
              onClick={() => onNavigate('history')}
              className="transition hover:text-[#D4AF5A]"
            >
              History
            </button>

            <button
              onClick={() => onNavigate('insights')}
              className="transition hover:text-[#D4AF5A]"
            >
              Insights
            </button>
          </div>

        </div>

      </footer>
    </div>
  );
};

export default Dashboard;