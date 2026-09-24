import React, { useState, useEffect, useRef } from 'react';
import {
  MessageSquare,
  Search,
  Activity,
  Sparkles,
  AlertCircle,
  Database,
  Target,
  BrainCircuit,
  Package,
} from 'lucide-react';

import { ReviewAnalysis, ReviewHistoryItem } from '../types/review';
import { ProductSummary, ProductAnalysisResponse } from '../types/ecommerce';
import {
  analyzeReview,
  checkBackendHealth,
  HealthStatus,
  API_BASE_URL,
  getProductAnalysis,
} from '../services/api';
import {
  fetchAllReviews,
  saveReviewAnalysis,
  deleteReviewById,
  clearAllReviews,
  getLocalReviews,
} from '../services/historyStorage';
import { isSupabaseConfigured, supabaseConfigurationError } from '../services/supabase';
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
import { DatasetExplorer } from '../components/DatasetExplorer';
import { EvaluationDashboard } from '../components/EvaluationDashboard';

type TabType = 'product_search' | 'live_analyzer' | 'dataset' | 'evaluation' | 'history';

export const Dashboard: React.FC = () => {
  // Navigation tabs
  const [activeTab, setActiveTab] = useState<TabType>('product_search');

  // Ecommerce Product Search State
  const [selectedProduct, setSelectedProduct] = useState<ProductSummary | null>(null);
  const [productAnalysis, setProductAnalysis] = useState<ProductAnalysisResponse | null>(null);
  const [loadingProduct, setLoadingProduct] = useState<boolean>(false);
  const [productError, setProductError] = useState<string | null>(null);

  // Custom live review analysis states
  const [currentAnalysis, setCurrentAnalysis] = useState<ReviewAnalysis | null>(null);
  const [activeReviewText, setActiveReviewText] = useState<string>('');
  const [isLoadingLive, setIsLoadingLive] = useState<boolean>(false);
  const [liveErrorMessage, setLiveErrorMessage] = useState<string | null>(null);

  // History state & storage source
  const [history, setHistory] = useState<ReviewHistoryItem[]>(() => getLocalReviews());
  const [storageSource, setStorageSource] = useState<'supabase' | 'local'>('local');

  // Backend Health check status
  const [healthStatus, setHealthStatus] = useState<HealthStatus | null>(null);

  const analysisRef = useRef<HTMLDivElement>(null);

  // Load reviews from Supabase or LocalStorage on mount
  const refreshHistory = async () => {
    const { reviews, source } = await fetchAllReviews();
    setHistory(reviews);
    setStorageSource(source);
  };

  useEffect(() => {
    refreshHistory();
  }, []);

  // Periodic health check
  useEffect(() => {
    const checkStatus = async () => {
      const status = await checkBackendHealth();
      setHealthStatus(status);
    };
    checkStatus();
    const interval = setInterval(checkStatus, 30000);
    return () => clearInterval(interval);
  }, []);

  // Load default initial product ("Electric Toothbrush") on first load
  useEffect(() => {
    handleSelectProduct({
      product_id: '9640962',
      product_title: 'Electric Toothbrush',
      category: 'Health & Personal Care',
      review_count: 125192,
      average_rating: 3.64,
    });
  }, []);

  // Handle Product Selection
  const handleSelectProduct = async (product: ProductSummary) => {
    setSelectedProduct(product);
    setLoadingProduct(true);
    setProductError(null);

    try {
      const res = await getProductAnalysis(product.product_id);
      setProductAnalysis(res);
    } catch (err: any) {
      setProductError(
        err.response?.data?.detail || 'Product not found in the available review dataset.'
      );
      setProductAnalysis(null);
    } finally {
      setLoadingProduct(false);
    }
  };

  // Handle Live Custom Review Analysis Submission
  const handleAnalyzeLive = async (reviewText: string) => {
    setIsLoadingLive(true);
    setLiveErrorMessage(null);
    setActiveReviewText(reviewText);

    try {
      const analysis = await analyzeReview(reviewText);
      setCurrentAnalysis(analysis);

      // Save to Supabase & localStorage via unified service
      const newItem = await saveReviewAnalysis(reviewText, analysis);
      setHistory((prev) => [newItem, ...prev.filter((i) => i.id !== newItem.id)]);
      if (isSupabaseConfigured) {
        setStorageSource('supabase');
      }

      setTimeout(() => {
        analysisRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }, 100);
    } catch (err: any) {
      setLiveErrorMessage(err.message || 'An error occurred while analyzing the review.');
    } finally {
      setIsLoadingLive(false);
    }
  };

  // History handlers
  const handleDeleteReview = async (id: string) => {
    try {
      await deleteReviewById(id);
      setHistory((prev) => prev.filter((item) => item.id !== id));
    } catch (err) {
      console.error('Failed to delete review:', err);
    }
  };

  const handleClearHistory = async () => {
    try {
      await clearAllReviews();
      setHistory([]);
    } catch (err) {
      console.error('Failed to clear history:', err);
    }
  };

  const handleSelectHistoryItem = (item: ReviewHistoryItem) => {
    setCurrentAnalysis(item.analysis);
    setActiveReviewText(item.reviewText);
    setActiveTab('live_analyzer');
    setTimeout(() => {
      analysisRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 100);
  };

  return (
    <div className="relative min-h-screen pb-16">
      {/* Background glow ambient effects */}
      <div className="glow-accent -top-40 -left-40 h-96 w-96 rounded-full bg-purple-600/30" />
      <div className="glow-accent top-1/3 -right-40 h-96 w-96 rounded-full bg-cyan-600/20" />
      <div className="glow-accent -bottom-40 left-1/4 h-96 w-96 rounded-full bg-indigo-600/20" />

      {/* Top Futuristic Header */}
      <header className="sticky top-0 z-40 border-b border-white/10 bg-[#080B11]/80 backdrop-blur-xl">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3 sm:px-6 lg:px-8">
          {/* Brand Logo & Title */}
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-tr from-purple-600 via-indigo-500 to-cyan-400 p-0.5 shadow-glow-purple">
              <div className="flex h-full w-full items-center justify-center rounded-[10px] bg-[#0B0F17]">
                <BrainCircuit className="h-5 w-5 text-purple-400" />
              </div>
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-base sm:text-lg font-extrabold tracking-wider text-white font-mono">
                  REVIEWIQ
                </h1>
                <span className="rounded bg-gradient-to-r from-purple-500/20 to-cyan-500/20 border border-purple-500/30 px-1.5 py-0.5 text-[10px] font-semibold text-purple-300 font-mono">
                  4M Dataset Engine
                </span>
                {isSupabaseConfigured && (
                  <span
                    className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium border ${
                      storageSource === 'supabase'
                        ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-400'
                        : 'border-cyan-500/30 bg-cyan-500/10 text-cyan-300'
                    }`}
                    title={
                      storageSource === 'supabase'
                        ? 'Connected to Supabase Cloud Database'
                        : 'Supabase configured (Syncing cache)'
                    }
                  >
                    <Database className="h-2.5 w-2.5" />
                    <span>Supabase DB</span>
                  </span>
                )}
              </div>
              <p className="text-[11px] sm:text-xs text-slate-400 hidden sm:block">
                Product Review Intelligence & Ground-Truth Dataset Analyzer
              </p>
            </div>
          </div>

          {/* Navigation Tabs */}
          <nav className="flex items-center gap-1 rounded-xl border border-slate-800 bg-[#111827]/80 p-1 overflow-x-auto max-w-full">
            <button
              onClick={() => setActiveTab('product_search')}
              className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold whitespace-nowrap transition ${
                activeTab === 'product_search'
                  ? 'bg-purple-600 text-white shadow-sm'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Search className="h-3.5 w-3.5" />
              <span>Product Intelligence</span>
            </button>
            <button
              onClick={() => setActiveTab('dataset')}
              className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold whitespace-nowrap transition ${
                activeTab === 'dataset'
                  ? 'bg-purple-600 text-white shadow-sm'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Database className="h-3.5 w-3.5" />
              <span>Dataset Explorer</span>
            </button>
            <button
              onClick={() => setActiveTab('live_analyzer')}
              className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold whitespace-nowrap transition ${
                activeTab === 'live_analyzer'
                  ? 'bg-purple-600 text-white shadow-sm'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <MessageSquare className="h-3.5 w-3.5" />
              <span>Live Review Analyzer</span>
            </button>
            <button
              onClick={() => setActiveTab('evaluation')}
              className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold whitespace-nowrap transition ${
                activeTab === 'evaluation'
                  ? 'bg-gradient-to-r from-purple-600 to-indigo-600 text-white shadow-sm'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Target className="h-3.5 w-3.5" />
              <span>AI Evaluation</span>
            </button>
            <button
              onClick={() => setActiveTab('history')}
              className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold whitespace-nowrap transition ${
                activeTab === 'history'
                  ? 'bg-purple-600 text-white shadow-sm'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Activity className="h-3.5 w-3.5" />
              <span>History ({history.length})</span>
            </button>
          </nav>
        </div>
      </header>

      {/* Main Container */}
      <main className="mx-auto max-w-7xl px-4 pt-6 sm:px-6 lg:px-8 space-y-8">
        {/* Backend Status Banners */}
        {healthStatus && healthStatus.status === 'offline' && (
          <div className="flex items-center gap-3 rounded-xl border border-rose-500/30 bg-rose-500/10 p-3.5 text-rose-300 text-xs">
            <AlertCircle className="h-4 w-4 shrink-0 text-rose-400" />
            <div className="flex-1">
              <strong>Backend Offline:</strong> Cannot connect to FastAPI backend at{' '}
              <code className="font-mono bg-rose-950/60 px-1 py-0.5 rounded">{API_BASE_URL}</code>.
              Please ensure the backend server is running.
            </div>
          </div>
        )}

        {/* TAB 1: PRODUCT INTELLIGENCE (Main Feature) */}
        {activeTab === 'product_search' && (
          <div className="space-y-8">
            {/* Search Header Section */}
            <section className="space-y-3">
              <div className="text-center max-w-2xl mx-auto space-y-2 mb-6">
                <h2 className="text-2xl sm:text-3xl font-black text-white tracking-tight">
                  Search & Analyze Product Reviews
                </h2>
                <p className="text-xs sm:text-sm text-slate-400">
                  Search any product title to retrieve its verified reviews, rating distributions, and AI synthesis from the 4M dataset.
                </p>
              </div>

              <div className="max-w-3xl mx-auto">
                <ProductSearch
                  onSelectProduct={handleSelectProduct}
                  selectedProductId={selectedProduct?.product_id}
                />
              </div>
            </section>

            {/* Product Overview & Review Analytics Display */}
            {loadingProduct ? (
              <div className="rounded-2xl border border-white/10 bg-[#111827]/80 p-16 text-center space-y-3">
                <div className="inline-block h-8 w-8 animate-spin rounded-full border-2 border-purple-400 border-t-transparent" />
                <p className="text-xs text-slate-400 font-mono">Retrieving actual dataset reviews & analytics...</p>
              </div>
            ) : productError ? (
              <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 p-8 text-center space-y-2">
                <AlertCircle className="h-8 w-8 text-rose-400 mx-auto" />
                <h3 className="text-sm font-bold text-rose-200">Product Not Found</h3>
                <p className="text-xs text-rose-300 max-w-md mx-auto">{productError}</p>
              </div>
            ) : productAnalysis ? (
              <div className="space-y-8 animate-fadeIn">
                {/* 1. Product Overview (Hero + Distributions) */}
                <ProductOverview analysis={productAnalysis} />

                {/* 2. Pros & Cons Analysis (Quantified & Traceable with Evidence Reviews) */}
                <ProsConsAnalysis
                  productId={productAnalysis.product.product_id}
                  productTitle={productAnalysis.product.product_title}
                />

                {/* 3. Personalized Recommendation, Suitability & Similar Product Comparison */}
                <PersonalizedRecommendation
                  productId={productAnalysis.product.product_id}
                  productTitle={productAnalysis.product.product_title}
                  onSelectAlternativeProduct={handleSelectProduct}
                />

                {/* 4. AI Executive Summary (Strictly constrained to retrieved reviews) */}
                <AISummaryCard productId={productAnalysis.product.product_id} />

                {/* 5. Actual Dataset Customer Reviews (Filterable & Paginated) */}
                <ReviewList
                  productId={productAnalysis.product.product_id}
                  productTitle={productAnalysis.product.product_title}
                />
              </div>
            ) : (
              <div className="rounded-2xl border border-dashed border-slate-800 p-12 text-center space-y-2">
                <Package className="h-8 w-8 text-slate-600 mx-auto" />
                <p className="text-sm font-semibold text-slate-300">Enter a product name above to analyze its reviews.</p>
                <p className="text-xs text-slate-500">
                  Select from popular products like "Electric Toothbrush" or "Stainless Steel Blender".
                </p>
              </div>
            )}
          </div>
        )}

        {/* TAB 2: DATASET EXPLORER */}
        {activeTab === 'dataset' && (
          <div className="space-y-6">
            <DatasetExplorer />
          </div>
        )}

        {/* TAB 3: LIVE CUSTOM REVIEW ANALYZER */}
        {activeTab === 'live_analyzer' && (
          <div className="space-y-6">
            <div className="space-y-1">
              <h2 className="text-lg font-bold text-white flex items-center gap-2">
                <Sparkles className="h-5 w-5 text-purple-400" />
                Live Custom Review Analyzer
              </h2>
              <p className="text-xs text-slate-400">
                Paste any unstructured customer feedback to extract structured sentiment, 1-5 star ratings, pros, cons, and summary using Gemini AI.
              </p>
            </div>

            {!isSupabaseConfigured && (
              <div className="flex items-start gap-3 rounded-xl border border-amber-500/30 bg-amber-500/10 p-3.5 text-amber-200 text-xs" role="status">
                <AlertCircle className="h-4 w-4 shrink-0 text-amber-400 mt-0.5" />
                <div>
                  <strong>Supabase persistence is not configured.</strong>{' '}
                  {supabaseConfigurationError || 'Set the frontend Supabase environment variables to save analyses to the reviews table.'}{' '}
                  Until then, new analyses are stored only in this browser&apos;s local history.
                </div>
              </div>
            )}

            <ReviewInput
              onAnalyze={handleAnalyzeLive}
              isLoading={isLoadingLive}
              errorMessage={liveErrorMessage}
              onClearError={() => setLiveErrorMessage(null)}
            />

            {isLoadingLive && <LoadingState message="Analyzing review with Gemini AI..." />}

            {currentAnalysis && !isLoadingLive && (
              <div ref={analysisRef} className="space-y-3">
                <div className="flex items-center justify-between">
                  <h3 className="text-xs font-semibold uppercase tracking-wider text-purple-400 font-mono flex items-center gap-1.5">
                    <Sparkles className="h-3.5 w-3.5" />
                    Analysis Assessment
                  </h3>
                </div>
                <AnalysisResult
                  analysis={currentAnalysis}
                  originalText={activeReviewText}
                />
              </div>
            )}
          </div>
        )}

        {/* TAB 4: AI EVALUATION & BENCHMARKING */}
        {activeTab === 'evaluation' && (
          <div className="space-y-6">
            <EvaluationDashboard />
          </div>
        )}

        {/* TAB 5: USER REVIEW HISTORY */}
        {activeTab === 'history' && (
          <div className="space-y-6">
            <ReviewHistory
              history={history}
              onSelectReview={handleSelectHistoryItem}
              onDeleteReview={handleDeleteReview}
              onClearHistory={handleClearHistory}
            />
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="mt-16 border-t border-slate-800/80 pt-8 text-center text-xs text-slate-400">
        <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
          <span className="font-mono font-bold text-slate-300">REVIEWIQ</span>
          <span className="hidden sm:inline text-slate-700">•</span>
          <span>4,000,000 Real Review Dataset Engine</span>
          <span className="hidden sm:inline text-slate-700">•</span>
          <span>Source: ReviewIQ Product Review Dataset</span>
        </div>
      </footer>
    </div>
  );
};
