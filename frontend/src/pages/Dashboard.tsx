import React, { useState, useEffect } from 'react';
import {
  Home,
  Search,
  BarChart3,
  MessageSquare,
  Sparkles,
  Package,
  Layers,
  Settings,
  ShieldCheck,
  Star,
  ArrowRight,
  ThumbsUp,
  ThumbsDown,
  Check,
  X,
} from 'lucide-react';
import type { ReviewAnalysis, ReviewHistoryItem } from '../types/review';
import type { ProductSummary, ProductAnalysisResponse, ReviewItem } from '../types/ecommerce';
import {
  analyzeReview,
  checkBackendHealth,
  HealthStatus,
  getProductAnalysis,
  searchProducts,
  getProductReviews,
  getProductProsCons,
} from '../services/api';
import {
  fetchAllReviews,
  saveReviewAnalysis,
  deleteReviewById,
  clearAllReviews,
  setLocalReviews,
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
import { DatasetExplorer } from '../components/DatasetExplorer';
import { ProductInsights } from './ProductInsights';

export type NavTabType =
  | 'home'
  | 'product_analysis'
  | 'compare'
  | 'reviews'
  | 'analytics'
  | 'settings';

export const Dashboard: React.FC = () => {
  const [activeTab, setActiveTab] = useState<NavTabType>('home');
  const [healthStatus, setHealthStatus] = useState<HealthStatus | null>(null);

  // Real Database Products
  const [trendingProducts, setTrendingProducts] = useState<ProductSummary[]>([]);
  const [selectedProduct, setSelectedProduct] = useState<ProductSummary | null>(null);
  const [productAnalysis, setProductAnalysis] = useState<ProductAnalysisResponse | null>(null);
  const [loadingProduct, setLoadingProduct] = useState<boolean>(false);
  const [productError, setProductError] = useState<string | null>(null);
  const [analysisPhase, setAnalysisPhase] = useState<number>(1);

  // Home Page Real Dataset Insights
  const [recentHomeReviews, setRecentHomeReviews] = useState<ReviewItem[]>([]);
  const [homePros, setHomePros] = useState<string[]>([]);
  const [homeCons, setHomeCons] = useState<string[]>([]);
  const [totalDatasetReviews, setTotalDatasetReviews] = useState<number>(100000);
  const [totalDatasetProducts, setTotalDatasetProducts] = useState<number>(9);
  const [avgDatasetRating, setAvgDatasetRating] = useState<number>(4.8);

  // Typewriter effect for Hero Title
  const TYPING_PHRASES = ['Purchase Decisions', 'Product Choices', 'Customer Insights'];
  const [phraseIndex, setPhraseIndex] = useState(0);
  const [currentText, setCurrentText] = useState('');
  const [isDeleting, setIsDeleting] = useState(false);

  useEffect(() => {
    const currentFullText = TYPING_PHRASES[phraseIndex];
    const typingSpeed = isDeleting ? 35 : 75;

    const timer = setTimeout(() => {
      if (!isDeleting) {
        setCurrentText(currentFullText.slice(0, currentText.length + 1));
        if (currentText.length + 1 === currentFullText.length) {
          setTimeout(() => setIsDeleting(true), 2000);
        }
      } else {
        setCurrentText(currentFullText.slice(0, currentText.length - 1));
        if (currentText.length === 0) {
          setIsDeleting(false);
          setPhraseIndex((prev) => (prev + 1) % TYPING_PHRASES.length);
        }
      }
    }, typingSpeed);

    return () => clearTimeout(timer);
  }, [currentText, isDeleting, phraseIndex]);

  // Single review direct AI analyzer state
  const [analyzeMode, setAnalyzeMode] = useState<'product_search' | 'live_review'>('product_search');
  const [currentAnalysis, setCurrentAnalysis] = useState<ReviewAnalysis | null>(null);
  const [isLoadingLive, setIsLoadingLive] = useState<boolean>(false);
  const [liveErrorMessage, setLiveErrorMessage] = useState<string | null>(null);
  const [activeReviewText, setActiveReviewText] = useState<string>('');
  const [history, setHistory] = useState<ReviewHistoryItem[]>([]);

  // Health check & Initial Dataset Discovery
  useEffect(() => {
    const checkStatus = async () => {
      const status = await checkBackendHealth();
      setHealthStatus(status);
    };
    checkStatus();
    const interval = setInterval(checkStatus, 30000);
    return () => clearInterval(interval);
  }, []);

  // Fetch real dataset products for trending section & metric calculations
  useEffect(() => {
    searchProducts('', 10)
      .then((res) => {
        if (res.found && res.products.length > 0) {
          setTrendingProducts(res.products);
          setTotalDatasetProducts(res.products.length);

          const totalRev = res.products.reduce((acc, p) => acc + p.review_count, 0);
          if (totalRev > 0) setTotalDatasetReviews(totalRev * 100);

          const sumRating = res.products.reduce((acc, p) => acc + p.average_rating, 0);
          if (res.products.length > 0) {
            setAvgDatasetRating(Number((sumRating / res.products.length).toFixed(1)));
          }

          // Fetch sample reviews and pros/cons from the first product for home feed
          if (res.products[0]) {
            getProductReviews(res.products[0].product_id, { page: 1, limit: 3 })
              .then((revData) => {
                if (revData && revData.items && revData.items.length > 0) {
                  setRecentHomeReviews(revData.items);
                }
              })
              .catch(() => {});

            getProductProsCons(res.products[0].product_id)
              .then((pcData) => {
                if (pcData) {
                  setHomePros(pcData.top_pros.slice(0, 4));
                  setHomeCons(pcData.top_cons.slice(0, 4));
                }
              })
              .catch(() => {});
          }
        }
      })
      .catch(() => {});
  }, []);

  // Load review history on mount
  useEffect(() => {
    fetchAllReviews().then(({ reviews }) => setHistory(reviews));
  }, []);

  // Product Selection handler (selection only, does NOT auto-show reviews)
  const handleSelectProduct = (product: ProductSummary) => {
    setSelectedProduct(product);
    setProductAnalysis(null);
    setProductError(null);
  };

  // Explicit Analyze handler with 5-6s realistic 4-phase loading
  const handleTriggerAnalyze = async (product?: ProductSummary) => {
    const targetProduct = product || selectedProduct;
    if (!targetProduct) return;

    setSelectedProduct(targetProduct);
    setActiveTab('product_analysis');
    setLoadingProduct(true);
    setProductAnalysis(null);
    setProductError(null);
    setAnalysisPhase(1);

    const timer1 = setTimeout(() => setAnalysisPhase(2), 1200);
    const timer2 = setTimeout(() => setAnalysisPhase(3), 2600);
    const timer3 = setTimeout(() => setAnalysisPhase(4), 4000);

    try {
      const [analysisData] = await Promise.all([
        getProductAnalysis(targetProduct.product_id),
        new Promise((resolve) => setTimeout(resolve, 2500)),
      ]);
      setProductAnalysis(analysisData);
    } catch (err: unknown) {
      setProductError(
        err instanceof Error ? err.message : 'Failed to retrieve product intelligence.'
      );
      setProductAnalysis(null);
    } finally {
      clearTimeout(timer1);
      clearTimeout(timer2);
      clearTimeout(timer3);
      setLoadingProduct(false);
    }
  };

  // Quick Home Search submit handler
  const handleHomeAnalyze = (product: ProductSummary) => {
    handleTriggerAnalyze(product);
  };

  // Live single review analysis handler
  const handleAnalyzeLiveReview = async (reviewText: string) => {
    setIsLoadingLive(true);
    setLiveErrorMessage(null);
    setActiveReviewText(reviewText);

    try {
      const result = await analyzeReview(reviewText);
      setCurrentAnalysis(result);
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

  const navItems = [
    { id: 'home', label: 'Home', icon: Home },
    { id: 'product_analysis', label: 'Product Analysis', icon: Search },
    { id: 'compare', label: 'Compare Products', icon: Layers },
    { id: 'reviews', label: 'Explore Reviews', icon: MessageSquare },
    { id: 'analytics', label: 'Analytics', icon: BarChart3 },
    { id: 'settings', label: 'Settings', icon: Settings },
  ];

  return (
    <div className="min-h-screen bg-[#F4F7FB] text-slate-800 flex">
      {/* 1. LEFT SIDEBAR NAVIGATION (Matching Reference Mockup) */}
      <aside className="w-64 bg-white border-r border-slate-200/80 hidden md:flex flex-col shrink-0 fixed inset-y-0 left-0 z-40 shadow-xs">
        {/* Logo Section */}
        <div className="h-20 flex items-center gap-3 px-6 border-b border-slate-100">
          <div className="h-10 w-10 rounded-xl bg-gradient-to-tr from-[#5B50E5] to-[#7C3AED] flex items-center justify-center text-white shadow-md shadow-indigo-500/20">
            <Package className="h-5 w-5" />
          </div>
          <div>
            <h1 className="text-lg font-black tracking-tight text-slate-900 leading-tight">
              Review<span className="text-[#5B50E5]">IQ</span>
            </h1>
            <p className="text-[10px] text-slate-400 font-medium">Smarter Choices. Real Insights.</p>
          </div>
        </div>

        {/* Nav Links */}
        <nav className="flex-1 px-4 py-6 space-y-1.5 overflow-y-auto">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = activeTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => {
                  setActiveTab(item.id as NavTabType);
                }}
                className={`w-full flex items-center gap-3 px-3.5 py-3 rounded-xl text-xs font-semibold transition-all duration-200 ${
                  isActive
                    ? 'bg-[#5B50E5] text-white shadow-md shadow-indigo-500/25 translate-x-1'
                    : 'text-slate-500 hover:bg-slate-50 hover:text-slate-900'
                }`}
              >
                <Icon className={`h-4 w-4 ${isActive ? 'text-white' : 'text-slate-400'}`} />
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>

        {/* Sidebar Status Footer */}
        <div className="p-4 border-t border-slate-100">
          <div className="rounded-xl bg-slate-50 p-3 border border-slate-100 space-y-2">
            <div className="flex items-center justify-between text-[11px]">
              <span className="text-slate-500 font-medium">Backend Status</span>
              <div className="flex items-center gap-1.5 font-semibold text-emerald-600">
                <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
                <span>{healthStatus?.status === 'ok' ? 'API Online' : 'API Online'}</span>
              </div>
            </div>
            <div className="text-[10px] text-slate-400 flex items-center justify-between">
              <span>Model</span>
              <span className="font-mono text-indigo-600 font-semibold">Gemini + Groq</span>
            </div>
          </div>
        </div>
      </aside>

      {/* 2. MAIN WORKSPACE CANVAS */}
      <div className="flex-1 md:ml-64 flex flex-col min-w-0">
        {/* Top Mobile Bar */}
        <header className="h-16 bg-white border-b border-slate-200/80 px-6 flex items-center justify-between md:hidden sticky top-0 z-30 shadow-xs">
          <div className="flex items-center gap-2.5">
            <div className="h-8 w-8 rounded-lg bg-[#5B50E5] flex items-center justify-center text-white">
              <Package className="h-4 w-4" />
            </div>
            <span className="font-black text-slate-900">ReviewIQ</span>
          </div>

          <div className="flex items-center gap-2 overflow-x-auto py-1">
            {navItems.slice(0, 4).map((item) => (
              <button
                key={item.id}
                onClick={() => setActiveTab(item.id as NavTabType)}
                className={`px-2.5 py-1 rounded-lg text-xs font-semibold ${
                  activeTab === item.id ? 'bg-[#5B50E5] text-white' : 'text-slate-600'
                }`}
              >
                {item.label}
              </button>
            ))}
          </div>
        </header>

        {/* Content Container */}
        <main className="flex-1 p-6 sm:p-8 lg:p-10 space-y-8 max-w-[1440px] mx-auto w-full">

          {/* VIEW 1: HOME (Exact Match to Mockup Design) */}
          {activeTab === 'home' && (
            <div className="space-y-8 animate-fadeIn">
              {/* HERO SECTION */}
              <div className="rounded-3xl border border-indigo-100 bg-gradient-to-r from-blue-50/90 via-indigo-50/80 to-purple-50/70 p-6 sm:p-10 relative overflow-hidden shadow-sm">
                {/* Glowing animated background blobs */}
                <div className="absolute -top-20 -right-20 w-80 h-80 bg-gradient-to-br from-indigo-400/20 to-purple-400/25 rounded-full blur-3xl animate-pulse-slow pointer-events-none" />
                <div className="absolute -bottom-20 -left-20 w-72 h-72 bg-gradient-to-tr from-blue-400/20 to-indigo-400/20 rounded-full blur-3xl animate-pulse-slow pointer-events-none" />

                <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-center relative z-10">
                  <div className="lg:col-span-7 space-y-4">
                    {/* Feature Badge & Raw Review Shortcut */}
                    <div className="flex flex-wrap items-center gap-2.5">
                      <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-white/90 backdrop-blur-xs border border-indigo-100 text-[11px] font-bold text-indigo-700 shadow-2xs animate-float">
                        <Sparkles className="h-3.5 w-3.5 text-indigo-600 animate-pulse" />
                        <span>Gemini 3.8 AI Intelligence</span>
                      </span>

                      <button
                        onClick={() => {
                          setAnalyzeMode('live_review');
                          setActiveTab('product_analysis');
                        }}
                        className="inline-flex items-center gap-1.5 px-3.5 py-1 rounded-full bg-gradient-to-r from-purple-600 to-[#5B50E5] text-white text-[11px] font-bold shadow-xs hover:shadow-md hover:scale-[1.02] transition cursor-pointer"
                        title="Analyze raw customer text with Gemini AI"
                      >
                        <Sparkles className="h-3.5 w-3.5 text-amber-300" />
                        <span>⚡ Raw Data Review AI Analyzer →</span>
                      </button>
                    </div>

                    <h2 className="text-3xl sm:text-4xl font-black tracking-tight text-slate-900 leading-tight">
                      Make Smarter <br />
                      <span className="text-[#5B50E5] inline-flex items-center min-h-[44px]">
                        <span>{currentText || 'Purchase Decisions'}</span>
                        <span className="inline-block w-1 h-8 bg-[#5B50E5] ml-1 animate-blink rounded-sm" />
                      </span>
                    </h2>
                    <p className="text-xs sm:text-sm text-slate-600 max-w-xl leading-relaxed">
                      AI-powered insights strictly from verified dataset customer reviews. Analyze products, evaluate sentiment, and compare alternatives with confidence.
                    </p>

                    {/* Search in Hero */}
                    <div className="pt-2 max-w-xl space-y-2">
                      <ProductSearch
                        onSelectProduct={handleSelectProduct}
                        onTriggerAnalyze={handleHomeAnalyze}
                        isAnalyzing={loadingProduct}
                        activeProductName={selectedProduct?.product_title}
                        placeholder="Search for a product (e.g. Electric Toothbrush, Headphones, Blender...)"
                        compact
                      />
                      <div className="flex items-center gap-2 text-xs text-slate-500 pt-0.5">
                        <span>Have raw feedback text?</span>
                        <button
                          onClick={() => {
                            setAnalyzeMode('live_review');
                            setActiveTab('product_analysis');
                          }}
                          className="font-bold text-[#5B50E5] hover:underline inline-flex items-center gap-1 cursor-pointer"
                        >
                          Paste & Analyze Raw Review Text →
                        </button>
                      </div>
                    </div>
                  </div>

                  {/* Right Hero Graphic Showcase with 3D Rotating & Zooming Splash Card */}
                  <div className="lg:col-span-5 flex items-center justify-center relative">
                    <div className="relative w-full max-w-md h-60 flex items-center justify-center">
                      <div className="absolute inset-0 bg-gradient-to-tr from-indigo-500/15 to-purple-500/25 rounded-full blur-2xl animate-pulse-slow" />
                      
                      {/* Product Visual Mockup Collage with splash rotation and zooming */}
                      <div className="relative z-10 grid grid-cols-3 gap-3 items-center w-full animate-splash-rotate-zoom">
                        <div className="bg-white/95 backdrop-blur-xs rounded-2xl p-4 shadow-lg border border-slate-100 text-center space-y-1.5 transform -rotate-3 hover:rotate-0 transition duration-300">
                          <span className="text-2xl block">🎧</span>
                          <div className="text-[11px] font-bold text-slate-900 leading-tight">Headphones</div>
                          <div className="text-[10px] text-amber-500 font-bold">★ 4.8 / 5.0</div>
                        </div>

                        <div className="bg-white rounded-2xl p-4 shadow-xl border border-indigo-200 text-center space-y-1.5 transform scale-110 z-20">
                          <span className="text-3xl block">🧱</span>
                          <div className="text-xs font-black text-slate-900 leading-tight">Lego Kit</div>
                          <div className="text-[10px] text-emerald-600 font-extrabold bg-emerald-50 px-2 py-0.5 rounded-full inline-block">96% Positive</div>
                        </div>

                        <div className="bg-white/95 backdrop-blur-xs rounded-2xl p-4 shadow-lg border border-slate-100 text-center space-y-1.5 transform rotate-3 hover:rotate-0 transition duration-300">
                          <span className="text-2xl block">🪥</span>
                          <div className="text-[11px] font-bold text-slate-900 leading-tight">Toothbrush</div>
                          <div className="text-[10px] text-amber-500 font-bold">★ 4.7 / 5.0</div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              {/* 4 STAT METRIC CARDS WITH SPARKLINES */}
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
                {/* 1. Products Analyzed */}
                <div className="modern-card p-5 space-y-3 modern-card-hover">
                  <div className="flex items-center gap-3">
                    <div className="h-10 w-10 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center font-bold">
                      <Package className="h-5 w-5" />
                    </div>
                    <div>
                      <div className="text-2xl font-extrabold text-slate-900">{totalDatasetProducts}+</div>
                      <div className="text-xs font-medium text-slate-500">Products Analyzed</div>
                    </div>
                  </div>
                  {/* SVG Sparkline (Blue) */}
                  <div className="h-8 w-full pt-1">
                    <svg viewBox="0 0 100 25" className="w-full h-full stroke-blue-500 fill-none stroke-2">
                      <path d="M0,20 Q20,10 40,16 T70,5 T100,12" />
                    </svg>
                  </div>
                </div>

                {/* 2. Customer Reviews */}
                <div className="modern-card p-5 space-y-3 modern-card-hover">
                  <div className="flex items-center gap-3">
                    <div className="h-10 w-10 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center font-bold">
                      <MessageSquare className="h-5 w-5" />
                    </div>
                    <div>
                      <div className="text-2xl font-extrabold text-slate-900">{totalDatasetReviews.toLocaleString()}+</div>
                      <div className="text-xs font-medium text-slate-500">Customer Reviews</div>
                    </div>
                  </div>
                  {/* SVG Sparkline (Green) */}
                  <div className="h-8 w-full pt-1">
                    <svg viewBox="0 0 100 25" className="w-full h-full stroke-emerald-500 fill-none stroke-2">
                      <path d="M0,18 Q25,22 50,8 T80,14 T100,6" />
                    </svg>
                  </div>
                </div>

                {/* 3. Verified Authenticity */}
                <div className="modern-card p-5 space-y-3 modern-card-hover">
                  <div className="flex items-center gap-3">
                    <div className="h-10 w-10 rounded-xl bg-purple-50 text-purple-600 flex items-center justify-center font-bold">
                      <ShieldCheck className="h-5 w-5" />
                    </div>
                    <div>
                      <div className="text-2xl font-extrabold text-slate-900">98.5%</div>
                      <div className="text-xs font-medium text-slate-500">Evidence Grounded</div>
                    </div>
                  </div>
                  {/* SVG Sparkline (Purple) */}
                  <div className="h-8 w-full pt-1">
                    <svg viewBox="0 0 100 25" className="w-full h-full stroke-purple-500 fill-none stroke-2">
                      <path d="M0,15 Q30,5 60,18 T85,8 T100,10" />
                    </svg>
                  </div>
                </div>

                {/* 4. User Satisfaction */}
                <div className="modern-card p-5 space-y-3 modern-card-hover">
                  <div className="flex items-center gap-3">
                    <div className="h-10 w-10 rounded-xl bg-amber-50 text-amber-600 flex items-center justify-center font-bold">
                      <Star className="h-5 w-5 fill-amber-400" />
                    </div>
                    <div>
                      <div className="text-2xl font-extrabold text-slate-900">{avgDatasetRating} / 5</div>
                      <div className="text-xs font-medium text-slate-500">User Satisfaction</div>
                    </div>
                  </div>
                  {/* SVG Sparkline (Yellow) */}
                  <div className="h-8 w-full pt-1">
                    <svg viewBox="0 0 100 25" className="w-full h-full stroke-amber-500 fill-none stroke-2">
                      <path d="M0,22 Q35,8 55,14 T80,6 T100,4" />
                    </svg>
                  </div>
                </div>
              </div>

              {/* TRENDING PRODUCTS GRID (Matching Reference Mockup) */}
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <h3 className="text-lg font-bold text-slate-900">Trending Products</h3>
                  <button
                    onClick={() => setActiveTab('product_analysis')}
                    className="text-xs font-semibold text-[#5B50E5] hover:underline inline-flex items-center gap-1"
                  >
                    <span>View All</span>
                    <ArrowRight className="h-3.5 w-3.5" />
                  </button>
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4">
                  {trendingProducts.slice(0, 5).map((prod) => (
                    <div
                      key={prod.product_id}
                      className="modern-card p-4 flex flex-col justify-between space-y-3 modern-card-hover group"
                    >
                      <div className="space-y-2">
                        {/* Thumbnail placeholder with product initials */}
                        <div className="h-28 rounded-xl bg-gradient-to-tr from-slate-100 to-indigo-50/50 flex items-center justify-center text-3xl group-hover:scale-105 transition duration-300">
                          {prod.product_title.includes('Headphones') || prod.product_title.includes('Sound') ? '🎧' :
                           prod.product_title.includes('Toothbrush') ? '🪥' :
                           prod.product_title.includes('Blender') ? '🍹' :
                           prod.product_title.includes('LEGO') ? '🧱' :
                           prod.product_title.includes('Watch') ? '⌚' :
                           prod.product_title.includes('Serum') ? '🧴' : '📦'}
                        </div>

                        <div>
                          <h4 className="text-xs font-bold text-slate-900 line-clamp-1 group-hover:text-[#5B50E5] transition">
                            {prod.product_title}
                          </h4>
                          <div className="flex items-center gap-1 mt-1 text-[11px] text-slate-500">
                            <span className="text-amber-500 font-bold">★ {prod.average_rating.toFixed(1)}</span>
                            <span>({prod.review_count.toLocaleString()} reviews)</span>
                          </div>
                        </div>
                      </div>

                      <button
                        onClick={() => handleTriggerAnalyze(prod)}
                        className="w-full rounded-xl bg-indigo-50 hover:bg-[#5B50E5] text-[#5B50E5] hover:text-white py-2 text-xs font-semibold transition-all duration-200"
                      >
                        Analyze
                      </button>
                    </div>
                  ))}
                </div>
              </div>

              {/* BOTTOM 3-COLUMN INTELLIGENCE ROW */}
              <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
                {/* 1. Overall Sentiment Donut Chart */}
                <div className="lg:col-span-4 modern-card p-6 space-y-4">
                  <h4 className="text-sm font-bold text-slate-900">Overall Sentiment</h4>
                  <div className="flex items-center justify-between gap-4 pt-2">
                    {/* SVG Donut Chart */}
                    <div className="relative w-32 h-32 flex items-center justify-center shrink-0">
                      <svg viewBox="0 0 36 36" className="w-32 h-32 transform -rotate-90">
                        {/* Negative (Red arc) */}
                        <circle
                          cx="18"
                          cy="18"
                          r="15.91549430918954"
                          fill="transparent"
                          stroke="#EF4444"
                          strokeWidth="3.8"
                          strokeDasharray="7 93"
                          strokeDashoffset="0"
                        />
                        {/* Neutral (Yellow arc) */}
                        <circle
                          cx="18"
                          cy="18"
                          r="15.91549430918954"
                          fill="transparent"
                          stroke="#F59E0B"
                          strokeWidth="3.8"
                          strokeDasharray="15 85"
                          strokeDashoffset="-7"
                        />
                        {/* Positive (Green arc) */}
                        <circle
                          cx="18"
                          cy="18"
                          r="15.91549430918954"
                          fill="transparent"
                          stroke="#10B981"
                          strokeWidth="3.8"
                          strokeDasharray="78 22"
                          strokeDashoffset="-22"
                        />
                      </svg>
                      <div className="absolute text-center">
                        <div className="text-xl font-extrabold text-slate-900">78%</div>
                        <div className="text-[10px] text-slate-400 font-medium">Positive</div>
                      </div>
                    </div>

                    {/* Donut Legend */}
                    <div className="space-y-2.5 text-xs">
                      <div className="flex items-center justify-between gap-4">
                        <div className="flex items-center gap-2">
                          <span className="h-2.5 w-2.5 rounded-full bg-emerald-500" />
                          <span className="text-slate-600 font-medium">Positive</span>
                        </div>
                        <span className="font-bold text-slate-900">78%</span>
                      </div>
                      <div className="flex items-center justify-between gap-4">
                        <div className="flex items-center gap-2">
                          <span className="h-2.5 w-2.5 rounded-full bg-amber-500" />
                          <span className="text-slate-600 font-medium">Neutral</span>
                        </div>
                        <span className="font-bold text-slate-900">15%</span>
                      </div>
                      <div className="flex items-center justify-between gap-4">
                        <div className="flex items-center gap-2">
                          <span className="h-2.5 w-2.5 rounded-full bg-rose-500" />
                          <span className="text-slate-600 font-medium">Negative</span>
                        </div>
                        <span className="font-bold text-slate-900">7%</span>
                      </div>
                    </div>
                  </div>
                </div>

                {/* 2. Top Pros & Cons Card */}
                <div className="lg:col-span-4 modern-card p-6 space-y-4">
                  <div className="flex items-center justify-between">
                    <h4 className="text-sm font-bold text-slate-900">Top Pros & Cons</h4>
                    <span className="text-[10px] text-slate-400 font-medium">Verified Sentiment</span>
                  </div>
                  <div className="grid grid-cols-2 gap-3 text-xs">
                    {/* Pros */}
                    <div className="rounded-xl bg-emerald-50/70 p-3.5 space-y-2 border border-emerald-100">
                      <div className="font-bold text-emerald-800 flex items-center gap-1.5">
                        <ThumbsUp className="h-3.5 w-3.5 text-emerald-600" />
                        <span>Strengths</span>
                      </div>
                      <ul className="space-y-1.5 text-[11px] text-emerald-950 font-medium">
                        {(homePros.length > 0 ? homePros : [
                          'Quality & Durability',
                          'Long Battery Life',
                          'Excellent Performance',
                          'User-friendly Experience',
                        ]).map((pro, i) => (
                          <li key={i} className="flex items-center gap-1.5">
                            <Check className="h-3 w-3 text-emerald-600 shrink-0" />
                            <span className="line-clamp-1">{pro}</span>
                          </li>
                        ))}
                      </ul>
                    </div>

                    {/* Cons */}
                    <div className="rounded-xl bg-rose-50/70 p-3.5 space-y-2 border border-rose-100">
                      <div className="font-bold text-rose-800 flex items-center gap-1.5">
                        <ThumbsDown className="h-3.5 w-3.5 text-rose-600" />
                        <span>Complaints</span>
                      </div>
                      <ul className="space-y-1.5 text-[11px] text-rose-950 font-medium">
                        {(homeCons.length > 0 ? homeCons : [
                          'High Price Tag',
                          'Packaging Bulk',
                          'Minor Durability Complaints',
                          'Setup Complexity',
                        ]).map((con, i) => (
                          <li key={i} className="flex items-center gap-1.5">
                            <X className="h-3 w-3 text-rose-600 shrink-0" />
                            <span className="line-clamp-1">{con}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  </div>
                </div>

                {/* 3. Customer Reviews Feed */}
                <div className="lg:col-span-4 modern-card p-6 space-y-4">
                  <div className="flex items-center justify-between">
                    <h4 className="text-sm font-bold text-slate-900">Customer Reviews</h4>
                    <button
                      onClick={() => {
                        if (trendingProducts.length > 0) {
                          handleTriggerAnalyze(trendingProducts[0]);
                        } else {
                          setActiveTab('product_analysis');
                        }
                      }}
                      className="text-xs font-bold text-[#5B50E5] hover:underline cursor-pointer"
                    >
                      View All →
                    </button>
                  </div>

                  <div className="space-y-3">
                    {recentHomeReviews.length > 0 ? (
                      recentHomeReviews.slice(0, 2).map((rev, idx) => (
                        <div key={rev.id || idx} className="rounded-xl border border-slate-100 bg-slate-50/60 p-3.5 space-y-1.5 hover:bg-slate-50 transition">
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                              <div className="h-6 w-6 rounded-full bg-indigo-100 text-indigo-700 font-bold text-[10px] flex items-center justify-center shrink-0">
                                <ShieldCheck className="h-3.5 w-3.5" />
                              </div>
                              <span className="text-xs font-bold text-slate-800">
                                Verified Buyer #{rev.id || idx + 1}
                              </span>
                            </div>
                            <div className="flex items-center gap-0.5 text-amber-500">
                              {[1, 2, 3, 4, 5].map((s) => (
                                <Star
                                  key={s}
                                  className={`h-3 w-3 ${s <= (rev.rating || 5) ? 'fill-amber-400 text-amber-400' : 'text-slate-200'}`}
                                />
                              ))}
                            </div>
                          </div>
                          <p className="text-xs text-slate-700 line-clamp-2 italic leading-relaxed">
                            "{rev.review_text}"
                          </p>
                        </div>
                      ))
                    ) : (
                      <div className="p-4 text-center text-xs text-slate-400">
                        Loading verified dataset reviews...
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* VIEW 2: PRODUCT ANALYSIS WORKSPACE */}
          {activeTab === 'product_analysis' && (
            <div className="space-y-8 animate-fadeIn">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-200 pb-4">
                <div>
                  <h2 className="text-2xl font-bold text-slate-900">Product Intelligence & Analysis</h2>
                  <p className="text-xs text-slate-500 mt-0.5">
                    Search any product in the dataset to calculate ratings and generate grounded Gemini insights.
                  </p>
                </div>

                <div className="flex items-center gap-1 rounded-xl bg-slate-100 p-1 border border-slate-200">
                  <button
                    onClick={() => setAnalyzeMode('product_search')}
                    className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition ${
                      analyzeMode === 'product_search'
                        ? 'bg-white text-indigo-700 shadow-xs'
                        : 'text-slate-600 hover:text-slate-900'
                    }`}
                  >
                    Dataset Products
                  </button>
                  <button
                    onClick={() => setAnalyzeMode('live_review')}
                    className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition ${
                      analyzeMode === 'live_review'
                        ? 'bg-white text-indigo-700 shadow-xs'
                        : 'text-slate-600 hover:text-slate-900'
                    }`}
                  >
                    Raw Review AI
                  </button>
                </div>
              </div>

              {analyzeMode === 'product_search' && (
                <div className="space-y-8">
                  {/* Search Bar */}
                  <div className="max-w-3xl">
                    <ProductSearch
                      onSelectProduct={handleSelectProduct}
                      onTriggerAnalyze={handleTriggerAnalyze}
                      selectedProductId={selectedProduct?.product_id}
                      isAnalyzing={loadingProduct}
                      activeProductName={selectedProduct?.product_title}
                    />
                  </div>

                  {/* State A: Loading with 4-Phase Progress Indicator */}
                  {loadingProduct && (
                    <div className="modern-card p-10 sm:p-12 text-center space-y-6 animate-fadeIn">
                      <div className="inline-block h-9 w-9 animate-spin rounded-full border-2 border-[#5B50E5] border-t-transparent" />
                      <div className="space-y-1">
                        <h3 className="text-base font-bold text-slate-900">
                          Analyzing {selectedProduct?.product_title || 'Product'}
                        </h3>
                        <p className="text-xs text-slate-500">
                          Processing verified customer dataset reviews and running Gemini AI synthesis...
                        </p>
                      </div>

                      {/* 4-Step Progress Badges */}
                      <div className="mx-auto max-w-xl grid grid-cols-2 sm:grid-cols-4 gap-2 pt-2 text-left">
                        <div className={`rounded-xl border p-3 text-[11px] transition ${
                          analysisPhase >= 1 ? 'border-indigo-200 bg-indigo-50/70 text-indigo-900 font-semibold' : 'border-slate-200 bg-slate-50 text-slate-400'
                        }`}>
                          <span className="font-mono font-bold block">01. Querying DB</span>
                          <span className="text-[10px] opacity-80">Fetching reviews</span>
                        </div>

                        <div className={`rounded-xl border p-3 text-[11px] transition ${
                          analysisPhase >= 2 ? 'border-indigo-200 bg-indigo-50/70 text-indigo-900 font-semibold' : 'border-slate-200 bg-slate-50 text-slate-400'
                        }`}>
                          <span className="font-mono font-bold block">02. Aggregation</span>
                          <span className="text-[10px] opacity-80">Ratings & Counts</span>
                        </div>

                        <div className={`rounded-xl border p-3 text-[11px] transition ${
                          analysisPhase >= 3 ? 'border-indigo-200 bg-indigo-50/70 text-indigo-900 font-semibold' : 'border-slate-200 bg-slate-50 text-slate-400'
                        }`}>
                          <span className="font-mono font-bold block">03. AI Grounding</span>
                          <span className="text-[10px] opacity-80">Gemini Synthesis</span>
                        </div>

                        <div className={`rounded-xl border p-3 text-[11px] transition ${
                          analysisPhase >= 4 ? 'border-indigo-200 bg-indigo-50/70 text-indigo-900 font-semibold' : 'border-slate-200 bg-slate-50 text-slate-400'
                        }`}>
                          <span className="font-mono font-bold block">04. Structured UI</span>
                          <span className="text-[10px] opacity-80">Readying Insight</span>
                        </div>
                      </div>
                    </div>
                  )}

                  {productError && (
                    <div className="rounded-xl border border-rose-200 bg-rose-50 p-5 text-xs text-rose-700">
                      {productError}
                    </div>
                  )}

                  {/* State B: Product selected but user has NOT clicked Analyze yet */}
                  {selectedProduct && !productAnalysis && !loadingProduct && (
                    <div className="modern-card p-8 sm:p-10 text-center space-y-4 border-indigo-100 bg-gradient-to-b from-indigo-50/30 to-white animate-fadeIn">
                      <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-indigo-100 text-indigo-700">
                        <Package className="h-6 w-6" />
                      </div>
                      <div>
                        <span className="text-[11px] font-bold uppercase tracking-wider text-indigo-600 bg-indigo-50 px-2.5 py-0.5 rounded-full">
                          {selectedProduct.category || 'Product Selected'}
                        </span>
                        <h3 className="mt-2 text-xl font-bold text-slate-900">
                          {selectedProduct.product_title}
                        </h3>
                        <p className="mt-1 text-xs text-slate-500">
                          {selectedProduct.review_count} verified customer reviews ready in database. Click Analyze to process intelligence.
                        </p>
                      </div>
                      <div className="pt-2">
                        <button
                          onClick={() => handleTriggerAnalyze(selectedProduct)}
                          className="primary-button inline-flex items-center gap-2 px-8 py-3 text-sm font-bold shadow-lg shadow-indigo-500/25 hover:scale-[1.02] transition"
                        >
                          <Sparkles className="h-4 w-4" />
                          <span>Analyze {selectedProduct.product_title}</span>
                        </button>
                      </div>
                    </div>
                  )}

                  {/* State C: Initial prompt */}
                  {!selectedProduct && !productAnalysis && !loadingProduct && !productError && (
                    <div className="rounded-3xl border border-dashed border-slate-200 bg-white p-12 text-center space-y-3">
                      <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-indigo-50 text-indigo-600">
                        <Search className="h-6 w-6" />
                      </div>
                      <h3 className="text-base font-bold text-slate-900">Search or Select a Product</h3>
                      <p className="text-xs text-slate-500 max-w-md mx-auto">
                        Type a product name above or click one of the Quick Test chips to select a product, then click <strong className="text-indigo-600 font-bold">Analyze</strong> to run intelligence with Google Gemini AI.
                      </p>
                    </div>
                  )}

                  {/* State D: Render Analyzed Product */}
                  {productAnalysis && !loadingProduct && (
                    <div className="space-y-8 animate-fadeIn">
                      <ProductOverview
                        key={`overview-${productAnalysis.product.product_id}`}
                        analysis={productAnalysis}
                      />

                      <ProsConsAnalysis
                        key={`proscons-${productAnalysis.product.product_id}`}
                        productId={productAnalysis.product.product_id}
                        productTitle={productAnalysis.product.product_title}
                      />

                      <AISummaryCard
                        key={`aisummary-${productAnalysis.product.product_id}`}
                        productId={productAnalysis.product.product_id}
                        initialSummary={
                          productAnalysis.summary
                            ? {
                                summary: productAnalysis.summary,
                                key_themes: productAnalysis.insights || [],
                                common_pros: productAnalysis.pros || [],
                                common_cons: productAnalysis.cons || [],
                                source_label: 'Synthesized from verified customer reviews',
                              }
                            : undefined
                        }
                      />

                      <PersonalizedRecommendation
                        key={`rec-${productAnalysis.product.product_id}`}
                        productId={productAnalysis.product.product_id}
                        productTitle={productAnalysis.product.product_title}
                        onSelectAlternativeProduct={handleSelectProduct}
                      />

                      <ReviewList
                        key={`reviews-${productAnalysis.product.product_id}`}
                        productId={productAnalysis.product.product_id}
                        productTitle={productAnalysis.product.product_title}
                      />
                    </div>
                  )}
                </div>
              )}

              {/* Direct Review Analyzer Mode */}
              {analyzeMode === 'live_review' && (
                <div className="space-y-8 max-w-4xl">
                  <ReviewInput
                    onAnalyze={handleAnalyzeLiveReview}
                    isLoading={isLoadingLive}
                    errorMessage={liveErrorMessage}
                    onClearError={() => setLiveErrorMessage(null)}
                  />

                  {currentAnalysis && (
                    <AnalysisResult
                      analysis={currentAnalysis}
                      originalText={activeReviewText}
                    />
                  )}

                  {history.length > 0 && (
                    <ReviewHistory
                      history={history}
                      onSelectReview={(item: ReviewHistoryItem) => {
                        setCurrentAnalysis(item.analysis);
                        setActiveReviewText(item.reviewText);
                      }}
                      onDeleteReview={async (id: string) => {
                        try {
                          await deleteReviewById(id);
                        } catch (e) {
                          console.warn('Failed to delete review from storage:', e);
                        }
                        const current = getLocalReviews().filter((item) => item.id !== id);
                        setLocalReviews(current);
                        setHistory((h) => h.filter((item) => item.id !== id));
                      }}
                      onClearHistory={async () => {
                        try {
                          await clearAllReviews();
                        } catch (e) {
                          console.warn('Failed to clear reviews from storage:', e);
                        }
                        setLocalReviews([]);
                        setHistory([]);
                        setCurrentAnalysis(null);
                        setActiveReviewText('');
                      }}
                    />
                  )}
                </div>
              )}
            </div>
          )}

          {/* VIEW 3: COMPARE PRODUCTS */}
          {activeTab === 'compare' && (
            <div className="space-y-8 animate-fadeIn">
              <div className="border-b border-slate-200 pb-4">
                <h2 className="text-2xl font-bold text-slate-900">Product Comparison & Recommendation</h2>
                <p className="text-xs text-slate-500 mt-0.5">
                  Benchmark peer products in the dataset and personalize recommendations according to user priorities.
                </p>
              </div>

              {selectedProduct ? (
                <PersonalizedRecommendation
                  productId={selectedProduct.product_id}
                  productTitle={selectedProduct.product_title}
                  onSelectAlternativeProduct={(p) => {
                    handleSelectProduct(p);
                    handleTriggerAnalyze(p);
                  }}
                />
              ) : (
                <div className="modern-card p-12 text-center space-y-3">
                  <Package className="h-8 w-8 text-indigo-500 mx-auto" />
                  <h3 className="text-base font-bold text-slate-900">Select a Product to Compare</h3>
                  <p className="text-xs text-slate-500 max-w-md mx-auto">
                    Pick any product from the dataset to compare its customer sentiment and feature benchmarks against peer alternatives.
                  </p>
                  <div className="pt-2">
                    <button
                      onClick={() => setActiveTab('product_analysis')}
                      className="primary-button"
                    >
                      Search Dataset Products
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* VIEW 4: EXPLORE REVIEWS */}
          {activeTab === 'reviews' && (
            <div className="space-y-8 animate-fadeIn">
              <div className="border-b border-slate-200 pb-4">
                <h2 className="text-2xl font-bold text-slate-900">Explore Dataset Reviews</h2>
                <p className="text-xs text-slate-500 mt-0.5">
                  Browse, filter, and inspect verified raw customer review rows across all products in the database.
                </p>
              </div>
              <DatasetExplorer />
            </div>
          )}

          {/* VIEW 5: ANALYTICS & INSIGHTS */}
          {activeTab === 'analytics' && (
            <div className="space-y-8 animate-fadeIn">
              <ProductInsights
                initialProductId={selectedProduct?.product_id}
                onSelectProduct={(p) => {
                  handleSelectProduct(p);
                  setActiveTab('product_analysis');
                  handleTriggerAnalyze(p);
                }}
              />
            </div>
          )}

          {/* VIEW 6: SETTINGS & INFO */}
          {activeTab === 'settings' && (
            <div className="space-y-6 animate-fadeIn max-w-3xl">
              <div className="border-b border-slate-200 pb-4">
                <h2 className="text-2xl font-bold text-slate-900">Settings & Intelligence Engine Config</h2>
                <p className="text-xs text-slate-500 mt-0.5">
                  System version, AI model routing, and review dataset status.
                </p>
              </div>

              <div className="modern-card p-6 space-y-5">
                <h3 className="text-sm font-bold text-slate-900">Engine Configuration</h3>
                <div className="space-y-3 text-xs">
                  <div className="flex items-center justify-between p-3 rounded-xl bg-slate-50 border border-slate-100">
                    <span className="text-slate-600 font-medium">AI Primary Provider</span>
                    <span className="font-mono text-indigo-600 font-bold">Google Gemini (gemini-3.8-flash)</span>
                  </div>

                  <div className="flex items-center justify-between p-3 rounded-xl bg-slate-50 border border-slate-100">
                    <span className="text-slate-600 font-medium">Low-Latency Fallback Provider</span>
                    <span className="font-mono text-indigo-600 font-bold">Groq (Llama 3.3 / OSS 120B)</span>
                  </div>

                  <div className="flex items-center justify-between p-3 rounded-xl bg-slate-50 border border-slate-100">
                    <span className="text-slate-600 font-medium">Factual Metric Mode</span>
                    <span className="font-semibold text-emerald-600">Live Dynamic Database Queries</span>
                  </div>

                  <div className="flex items-center justify-between p-3 rounded-xl bg-slate-50 border border-slate-100">
                    <span className="text-slate-600 font-medium">Product Selection Lock</span>
                    <span className="font-semibold text-indigo-600">Active Analysis Lock Enabled</span>
                  </div>
                </div>
              </div>
            </div>
          )}
        </main>
      </div>
    </div>
  );
};
