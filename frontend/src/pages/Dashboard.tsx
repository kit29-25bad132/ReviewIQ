import React, { useState, useEffect } from 'react';
import {
  ArrowRight,
  BarChart3,
  FileSearch,
  Search,
  Sparkles,
  TrendingUp,
  Package,
} from 'lucide-react';
import type { ReviewAnalysis, ReviewHistoryItem } from '../types/review';
import type { ProductSummary, ProductAnalysisResponse } from '../types/ecommerce';
import {
  analyzeReview,
  checkBackendHealth,
  HealthStatus,
  getProductAnalysis,
} from '../services/api';
import {
  fetchAllReviews,
  saveReviewAnalysis,
  deleteReviewById,
  clearAllReviews,
  getLocalReviews,
} from '../services/historyStorage';
import { ProductSearch } from '../components/ProductSearch';
import { ProductOverview } from '../components/ProductOverview';
import { ProsConsAnalysis } from '../components/ProsConsAnalysis';
import { PersonalizedRecommendation } from '../components/PersonalizedRecommendation';
import { AISummaryCard } from '../components/AISummaryCard';
import { ReviewList } from '../components/ReviewList';
import { ReviewInput } from '../components/ReviewInput';
import { AnalysisResult } from '../components/AnalysisResult';
import { ReviewHistory } from '../components/ReviewHistory';
import { LoadingState } from '../components/LoadingState';
import { ProductInsights } from './ProductInsights';

export type TabType = 'home' | 'analyze' | 'history' | 'insights';

const features = [
  {
    icon: FileSearch,
    title: 'Review Analysis',
    description:
      'Turn customer reviews into structured product intelligence with sentiment, ratings, and evidence.',
  },
  {
    icon: TrendingUp,
    title: 'Sentiment & Trends',
    description:
      'Identify recurring opinions, aspect-level distributions, and emerging product issues in real time.',
  },
  {
    icon: BarChart3,
    title: 'Product Insights',
    description:
      'Understand the strengths and pain points customers care about most from actual dataset reviews.',
  },
];

export const Dashboard: React.FC = () => {
  const [activeTab, setActiveTab] = useState<TabType>('home');

  // Analyze tab mode: 'product_search' | 'live_review'
  const [analyzeMode, setAnalyzeMode] = useState<'product_search' | 'live_review'>('product_search');

  // Selected Product State
  const [selectedProduct, setSelectedProduct] = useState<ProductSummary | null>(null);
  const [productAnalysis, setProductAnalysis] = useState<ProductAnalysisResponse | null>(null);
  const [loadingProduct, setLoadingProduct] = useState<boolean>(false);
  const [productError, setProductError] = useState<string | null>(null);

  // Live single review analysis state
  const [currentAnalysis, setCurrentAnalysis] = useState<ReviewAnalysis | null>(null);
  const [activeReviewText, setActiveReviewText] = useState<string>('');
  const [isLoadingLive, setIsLoadingLive] = useState<boolean>(false);
  const [liveErrorMessage, setLiveErrorMessage] = useState<string | null>(null);

  // History state & storage source
  const [history, setHistory] = useState<ReviewHistoryItem[]>(() => getLocalReviews());
  const [storageSource, setStorageSource] = useState<'supabase' | 'local'>('local');

  // Backend Health check status
  const [healthStatus, setHealthStatus] = useState<HealthStatus | null>(null);

  // Home page featured preview product analysis
  const [featuredAnalysis, setFeaturedAnalysis] = useState<ProductAnalysisResponse | null>(null);

  // Load reviews on mount
  const refreshHistory = async () => {
    const { reviews, source } = await fetchAllReviews();
    setHistory(reviews);
    setStorageSource(source);
  };

  useEffect(() => {
    refreshHistory();
  }, []);

  // Health check
  useEffect(() => {
    const checkStatus = async () => {
      const status = await checkBackendHealth();
      setHealthStatus(status);
    };
    checkStatus();
    const interval = setInterval(checkStatus, 30000);
    return () => clearInterval(interval);
  }, []);

  // Load featured preview product for Hero card
  useEffect(() => {
    getProductAnalysis('9640962')
      .then((res) => {
        setFeaturedAnalysis(res);
      })
      .catch(() => {
        // Fallback if not ready
      });
  }, []);

  // Handle product selection in Analyze tab
  const handleSelectProduct = async (product: ProductSummary) => {
    setSelectedProduct(product);
    setLoadingProduct(true);
    setProductError(null);
    try {
      const analysisData = await getProductAnalysis(product.product_id);
      setProductAnalysis(analysisData);
    } catch (err: unknown) {
      setProductError(
        err instanceof Error ? err.message : 'Failed to retrieve product intelligence.'
      );
      setProductAnalysis(null);
    } finally {
      setLoadingProduct(false);
    }
  };

  // Load initial product when switching to Analyze tab if none selected
  useEffect(() => {
    if (activeTab === 'analyze' && !selectedProduct) {
      handleSelectProduct({
        product_id: '9640962',
        product_title: 'Electric Toothbrush',
        category: 'Health & Personal Care',
        review_count: 11,
        average_rating: 3.64,
      });
    }
  }, [activeTab]);

  // Live single review analysis submit handler
  const handleAnalyzeLiveReview = async (reviewText: string) => {
    setIsLoadingLive(true);
    setLiveErrorMessage(null);
    setActiveReviewText(reviewText);

    try {
      const result = await analyzeReview(reviewText);
      setCurrentAnalysis(result);

      // Persist to Supabase or LocalStorage
      const savedItem = await saveReviewAnalysis(reviewText, result);
      setHistory((prev) => [savedItem, ...prev]);
    } catch (err: unknown) {
      const msg =
        err instanceof Error ? err.message : 'AI review analysis failed. Please try again.';
      setLiveErrorMessage(msg);
      setCurrentAnalysis(null);
    } finally {
      setIsLoadingLive(false);
    }
  };

  // History delete handlers
  const handleDeleteHistoryItem = async (id: string) => {
    await deleteReviewById(id);
    setHistory((prev) => prev.filter((item) => item.id !== id));
  };

  const handleClearAllHistory = async () => {
    await clearAllReviews();
    setHistory([]);
  };

  return (
    <div className="min-h-screen bg-[#0E0F10] text-[#F5F2EA]">
      {/* Navigation Header */}
      <header className="sticky top-0 z-50 border-b border-[#292A2B]/80 bg-[#0E0F10]/95 backdrop-blur">
        <div className="mx-auto flex h-[74px] max-w-[1280px] items-center justify-between px-6 sm:px-8 lg:px-10">
          {/* Logo */}
          <button
            onClick={() => setActiveTab('home')}
            className="flex items-center gap-3 text-left focus:outline-none group"
          >
            <div className="relative flex h-10 w-10 items-center justify-center overflow-hidden rounded-xl border border-[#D4AF5A]/40 bg-[#191714] shadow-md transition group-hover:border-[#D4AF5A]">
              <img src="/logo.png" alt="ReviewIQ Logo" className="h-full w-full object-cover" />
            </div>

            <div>
              <p className="text-[15px] font-semibold tracking-[0.18em]">
                REVIEW<span className="text-[#D4AF5A]">IQ</span>
              </p>
              <p className="text-[8px] uppercase tracking-[0.2em] text-[#74736E]">
                Product Intelligence
              </p>
            </div>
          </button>

          {/* Navigation Links */}
          <nav className="hidden items-center gap-8 md:flex">
            <button
              onClick={() => setActiveTab('home')}
              className={`text-xs transition ${
                activeTab === 'home'
                  ? 'text-[#F0D58A] font-semibold'
                  : 'text-[#92908A] hover:text-[#F5F2EA]'
              }`}
            >
              Home
            </button>

            <button
              onClick={() => setActiveTab('analyze')}
              className={`text-xs transition ${
                activeTab === 'analyze'
                  ? 'text-[#F0D58A] font-semibold'
                  : 'text-[#92908A] hover:text-[#F5F2EA]'
              }`}
            >
              Analyze
            </button>

            <button
              onClick={() => setActiveTab('history')}
              className={`text-xs transition ${
                activeTab === 'history'
                  ? 'text-[#F0D58A] font-semibold'
                  : 'text-[#92908A] hover:text-[#F5F2EA]'
              }`}
            >
              History
            </button>

            <button
              onClick={() => setActiveTab('insights')}
              className={`text-xs transition ${
                activeTab === 'insights'
                  ? 'text-[#F0D58A] font-semibold'
                  : 'text-[#92908A] hover:text-[#F5F2EA]'
              }`}
            >
              Insights
            </button>
          </nav>

          {/* Right Action: Health Status & Get Started */}
          <div className="flex items-center gap-4">
            {healthStatus && (
              <div
                className="hidden sm:flex items-center gap-1.5 rounded-full border border-[#292A2B] bg-[#151617] px-2.5 py-1 text-[10px] font-mono text-[#AAA79F]"
                title={`FastAPI backend: ${healthStatus.status}`}
              >
                <span
                  className={`h-2 w-2 rounded-full ${
                    healthStatus.status === 'ok' ? 'bg-emerald-400 animate-pulse' : 'bg-amber-400'
                  }`}
                />
                <span>API {healthStatus.status === 'ok' ? 'Online' : 'Offline'}</span>
              </div>
            )}

            <button
              onClick={() => {
                setActiveTab('analyze');
                setAnalyzeMode('product_search');
              }}
              className="gold-button inline-flex items-center gap-2 px-4 py-2 text-xs font-semibold"
            >
              Get Started
              <ArrowRight className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
      </header>

      {/* Main Views Router */}
      <main>
        {/* VIEW 1: HOME PAGE */}
        {activeTab === 'home' && (
          <div>
            {/* Hero Section */}
            <section className="relative overflow-hidden">
              <div className="mx-auto max-w-[1280px] px-6 pb-20 pt-16 sm:px-8 sm:pt-24 lg:px-10 lg:pb-28 lg:pt-28">
                <div className="grid items-center gap-14 lg:grid-cols-[1.05fr_0.95fr]">
                  {/* Hero Left Content */}
                  <div>
                    <div className="mb-6 flex items-center gap-3">
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
                      <span className="text-[#D4AF5A]">intelligence.</span>
                    </h1>

                    <p className="mt-7 max-w-xl text-sm leading-7 text-[#8B8982] sm:text-base">
                      ReviewIQ helps you understand what customers really think
                      about a product by transforming reviews into clear,
                      structured insights.
                    </p>

                    <div className="mt-9 flex flex-col gap-3 sm:flex-row">
                      <button
                        onClick={() => {
                          setActiveTab('analyze');
                          setAnalyzeMode('product_search');
                        }}
                        className="gold-button inline-flex items-center justify-center gap-2 px-6 py-3.5 text-sm font-semibold"
                      >
                        <Search className="h-4 w-4" />
                        Analyze a Product
                        <ArrowRight className="h-4 w-4" />
                      </button>

                      <button
                        onClick={() => setActiveTab('insights')}
                        className="inline-flex items-center justify-center gap-2 rounded-[10px] border border-[#292A2B] bg-[#151617] px-6 py-3.5 text-sm text-[#AAA79F] transition hover:border-[#D4AF5A]/30 hover:text-[#F5F2EA]"
                      >
                        Explore Insights
                      </button>
                    </div>
                  </div>

                  {/* Hero Right: Live Product Intelligence Preview Card */}
                  <div className="relative">
                    <div className="premium-panel relative overflow-hidden p-6 sm:p-8">
                      <div className="absolute right-0 top-0 h-32 w-32 rounded-bl-full border-b border-l border-[#D4AF5A]/10 pointer-events-none" />

                      <div className="relative">
                        <div className="flex items-center justify-between border-b border-[#292A2B] pb-5">
                          <div>
                            <p className="text-[10px] uppercase tracking-[0.18em] text-[#74736E]">
                              Product analysis
                            </p>
                            <p className="mt-1.5 text-sm font-medium text-[#F5F2EA]">
                              {featuredAnalysis?.product.product_title || 'Electric Toothbrush'}
                            </p>
                          </div>

                          <span className="rounded-full border border-[#D4AF5A]/20 bg-[#1B1915] px-2.5 py-1 text-[9px] uppercase tracking-[0.12em] text-[#D4AF5A]">
                            AI analyzed
                          </span>
                        </div>

                        <div className="py-6">
                          <p className="text-xs text-[#74736E]">Overall rating</p>
                          <div className="mt-1.5 flex items-end gap-3">
                            <span className="text-4xl font-medium text-[#F5F2EA]">
                              {featuredAnalysis?.statistics.average_rating.toFixed(1) || '4.5'}
                            </span>
                            <span className="mb-1 text-xs text-[#D4AF5A]">/ 5</span>
                          </div>
                        </div>

                        <div className="space-y-3 border-t border-[#292A2B] pt-5">
                          {[
                            ['Quality & Durability', '4.7', 'Positive'],
                            ['Value for Money', '4.5', 'Positive'],
                            ['Battery Life', '3.8', 'Mixed'],
                            ['Ease of Use', '4.6', 'Positive'],
                          ].map(([name, rating, sentiment]) => (
                            <div key={name} className="flex items-center justify-between text-xs">
                              <span className="text-[#AAA79F]">{name}</span>
                              <div className="flex items-center gap-3">
                                <span className="text-[#F5F2EA] font-mono">{rating}</span>
                                <span className="text-[10px] text-[#D4AF5A] font-medium">{sentiment}</span>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>

                    <div className="absolute -bottom-4 -left-4 hidden rounded-xl border border-[#292A2B] bg-[#151617] px-4 py-3 shadow-2xl sm:block">
                      <p className="text-[9px] uppercase tracking-[0.15em] text-[#74736E]">
                        Reviews analyzed
                      </p>
                      <p className="mt-0.5 text-lg font-medium text-[#F5F2EA]">
                        {featuredAnalysis?.statistics.review_count.toLocaleString() || '156'}
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

            {/* How it works Section */}
            <section className="mx-auto max-w-[1280px] px-6 py-20 sm:px-8 lg:px-10 lg:py-24">
              <div className="max-w-2xl">
                <p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-[#D4AF5A]">
                  How ReviewIQ works
                </p>
                <h2 className="mt-4 text-3xl font-medium tracking-[-0.03em] sm:text-4xl">
                  From reviews to <span className="text-[#AAA79F]">useful insight.</span>
                </h2>
              </div>

              <div className="mt-12 grid gap-0 border-y border-[#292A2B] md:grid-cols-3">
                {[
                  {
                    number: '01',
                    title: 'Search a product',
                    text: 'Find any product from the available review dataset instantly.',
                  },
                  {
                    number: '02',
                    title: 'Analyze reviews',
                    text: 'ReviewIQ processes customer feedback, rating distributions, and recurring themes.',
                  },
                  {
                    number: '03',
                    title: 'Discover insights',
                    text: 'Explore evidence-backed pros, cons, executive summaries, and related comparisons.',
                  },
                ].map((item, index) => (
                  <div
                    key={item.number}
                    className={`px-6 py-8 sm:px-8 md:py-10 ${
                      index !== 2 ? 'border-b border-[#292A2B] md:border-b-0 md:border-r' : ''
                    }`}
                  >
                    <span className="text-[10px] font-mono tracking-[0.18em] text-[#D4AF5A]">
                      {item.number}
                    </span>
                    <h3 className="mt-6 text-lg font-medium text-[#F5F2EA]">{item.title}</h3>
                    <p className="mt-3 text-xs leading-6 text-[#8B8982]">{item.text}</p>
                  </div>
                ))}
              </div>
            </section>

            {/* Features Highlight Section */}
            <section className="border-t border-[#292A2B]/80 bg-[#111213]/40 py-20 sm:py-24">
              <div className="mx-auto max-w-[1280px] px-6 sm:px-8 lg:px-10">
                <div className="grid gap-6 md:grid-cols-3">
                  {features.map((feat) => {
                    const Icon = feat.icon;
                    return (
                      <div
                        key={feat.title}
                        className="premium-panel p-8 space-y-4 hover:border-[#D4AF5A]/30 transition"
                      >
                        <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-[#D4AF5A]/30 bg-[#1B1915] text-[#D4AF5A]">
                          <Icon className="h-5 w-5" />
                        </div>
                        <h3 className="text-base font-medium text-[#F5F2EA]">{feat.title}</h3>
                        <p className="text-xs leading-relaxed text-[#AAA79F]">{feat.description}</p>
                      </div>
                    );
                  })}
                </div>
              </div>
            </section>

            {/* CTA Banner */}
            <section className="mx-auto max-w-[1280px] px-6 py-20 sm:px-8 lg:px-10">
              <div className="premium-panel p-8 sm:p-12 text-center space-y-5 relative overflow-hidden">
                <div className="absolute inset-0 bg-gradient-to-r from-[#D4AF5A]/5 via-transparent to-[#D4AF5A]/5 pointer-events-none" />
                <h2 className="text-2xl sm:text-3xl font-medium tracking-tight text-[#F5F2EA]">
                  Ready to turn customer feedback into intelligence?
                </h2>
                <p className="text-xs sm:text-sm text-[#AAA79F] max-w-xl mx-auto">
                  Start searching products in the verified review dataset or analyze raw customer review text with Google Gemini AI.
                </p>
                <div className="pt-2">
                  <button
                    onClick={() => {
                      setActiveTab('analyze');
                      setAnalyzeMode('product_search');
                    }}
                    className="gold-button px-8 py-3.5 text-xs sm:text-sm font-semibold inline-flex items-center gap-2"
                  >
                    <Search className="h-4 w-4" />
                    <span>Analyze a Product Now</span>
                  </button>
                </div>
              </div>
            </section>

            {/* Footer */}
            <footer className="border-t border-[#292A2B] py-8 text-center text-xs text-[#74736E]">
              <div className="mx-auto max-w-[1280px] px-6 flex flex-col sm:flex-row items-center justify-between gap-4">
                <div className="flex items-center gap-2.5">
                  <img src="/logo.png" alt="ReviewIQ" className="h-5 w-5 rounded-md object-cover" />
                  <p>© 2026 ReviewIQ — Product Intelligence Engine. Built with React & FastAPI.</p>
                </div>
                <div className="flex items-center gap-6">
                  <button onClick={() => setActiveTab('home')} className="hover:text-[#F5F2EA]">Home</button>
                  <button onClick={() => setActiveTab('analyze')} className="hover:text-[#F5F2EA]">Analyze</button>
                  <button onClick={() => setActiveTab('history')} className="hover:text-[#F5F2EA]">History</button>
                  <button onClick={() => setActiveTab('insights')} className="hover:text-[#F5F2EA]">Insights</button>
                </div>
              </div>
            </footer>
          </div>
        )}

        {/* VIEW 2: ANALYZE PAGE */}
        {activeTab === 'analyze' && (
          <div className="mx-auto max-w-[1280px] px-6 sm:px-8 lg:px-10 py-8 space-y-8">
            {/* Top Sub-Navigation Toggle */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-[#292A2B] pb-6">
              <div>
                <span className="text-[10px] font-semibold uppercase tracking-[0.25em] text-[#D4AF5A]">
                  ReviewIQ Engine
                </span>
                <h1 className="mt-1 text-2xl sm:text-3xl font-medium text-[#F5F2EA]">
                  {analyzeMode === 'product_search'
                    ? 'Product Search & Intelligence'
                    : 'Direct Review AI Analyzer'}
                </h1>
                <p className="mt-1 text-xs text-[#AAA79F]">
                  {analyzeMode === 'product_search'
                    ? 'Search real products from the review dataset to extract structured insights and comparisons.'
                    : 'Paste any unstructured customer review to extract sentiment, ratings, pros, and cons with Gemini.'}
                </p>
              </div>

              {/* Toggle Mode */}
              <div className="flex items-center gap-1 self-start rounded-xl border border-[#292A2B] bg-[#151617] p-1 shrink-0">
                <button
                  onClick={() => setAnalyzeMode('product_search')}
                  className={`inline-flex items-center gap-1.5 rounded-lg px-4 py-2 text-xs font-semibold transition ${
                    analyzeMode === 'product_search'
                      ? 'border border-[#D4AF5A]/50 bg-[#1B1915] text-[#F0D58A]'
                      : 'text-[#AAA79F] hover:text-[#F5F2EA]'
                  }`}
                >
                  <Package className="h-3.5 w-3.5" />
                  <span>Product Search</span>
                </button>

                <button
                  onClick={() => setAnalyzeMode('live_review')}
                  className={`inline-flex items-center gap-1.5 rounded-lg px-4 py-2 text-xs font-semibold transition ${
                    analyzeMode === 'live_review'
                      ? 'border border-[#D4AF5A]/50 bg-[#1B1915] text-[#F0D58A]'
                      : 'text-[#AAA79F] hover:text-[#F5F2EA]'
                  }`}
                >
                  <Sparkles className="h-3.5 w-3.5" />
                  <span>Direct Review AI</span>
                </button>
              </div>
            </div>

            {/* Mode A: Real Product Search Flow */}
            {analyzeMode === 'product_search' && (
              <div className="space-y-8">
                {/* Search Box */}
                <div className="max-w-3xl">
                  <ProductSearch
                    onSelectProduct={handleSelectProduct}
                    selectedProductId={selectedProduct?.product_id}
                  />
                </div>

                {loadingProduct && (
                  <div className="premium-panel p-16 text-center space-y-3">
                    <div className="inline-block h-6 w-6 animate-spin rounded-full border-2 border-[#D4AF5A] border-t-transparent" />
                    <p className="text-xs text-[#AAA79F]">
                      Retrieving dataset reviews & calculating ratings...
                    </p>
                  </div>
                )}

                {productError && (
                  <div className="rounded-xl border border-rose-900/40 bg-rose-950/20 p-5 text-xs text-rose-300">
                    {productError}
                  </div>
                )}

                {productAnalysis && !loadingProduct && (
                  <div className="space-y-8 animate-fadeIn">
                    {/* 1. Overview */}
                    <ProductOverview analysis={productAnalysis} />

                    {/* 2. Pros & Cons Analysis */}
                    <ProsConsAnalysis
                      productId={productAnalysis.product.product_id}
                      productTitle={productAnalysis.product.product_title}
                    />

                    {/* 3. AI Review Summary */}
                    <AISummaryCard productId={productAnalysis.product.product_id} />

                    {/* 4. Related Product Comparison */}
                    <PersonalizedRecommendation
                      productId={productAnalysis.product.product_id}
                      productTitle={productAnalysis.product.product_title}
                      onSelectAlternativeProduct={handleSelectProduct}
                    />

                    {/* 5. Customer Reviews List */}
                    <ReviewList
                      productId={productAnalysis.product.product_id}
                      productTitle={productAnalysis.product.product_title}
                    />
                  </div>
                )}
              </div>
            )}

            {/* Mode B: Direct Review AI Analyzer Flow */}
            {analyzeMode === 'live_review' && (
              <div className="space-y-8 max-w-4xl">
                <ReviewInput
                  onAnalyze={handleAnalyzeLiveReview}
                  isLoading={isLoadingLive}
                  errorMessage={liveErrorMessage}
                  onClearError={() => setLiveErrorMessage(null)}
                />

                {isLoadingLive && <LoadingState message="Extracting structured intelligence with Gemini..." />}

                {currentAnalysis && !isLoadingLive && (
                  <div className="animate-fadeIn">
                    <AnalysisResult
                      analysis={currentAnalysis}
                      originalText={activeReviewText}
                    />
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* VIEW 3: HISTORY PAGE */}
        {activeTab === 'history' && (
          <div className="mx-auto max-w-[1280px] px-6 sm:px-8 lg:px-10 py-8 space-y-8">
            <ReviewHistory
              history={history}
              onDeleteReview={handleDeleteHistoryItem}
              onClearHistory={handleClearAllHistory}
              storageSource={storageSource}
            />
          </div>
        )}

        {/* VIEW 4: INSIGHTS PAGE */}
        {activeTab === 'insights' && (
          <ProductInsights onBack={() => setActiveTab('home')} />
        )}
      </main>
    </div>
  );
};

export default Dashboard;
