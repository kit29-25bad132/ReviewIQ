import React, { useState, useEffect, useMemo, useRef } from 'react';
import {
  MessageSquare,
  ThumbsUp,
  ThumbsDown,
  MinusCircle,
  Star,
  Activity,
  Layers,
  Sparkles,
  BarChart3,
  CheckCircle,
  AlertCircle,
  ShieldCheck,
  Database,
  RefreshCw,
} from 'lucide-react';

import { ReviewAnalysis, ReviewHistoryItem, DashboardStats } from '../types/review';
import { analyzeReview, checkBackendHealth, HealthStatus, API_BASE_URL } from '../services/api';
import {
  fetchAllReviews,
  saveReviewAnalysis,
  deleteReviewById,
  clearAllReviews,
  getLocalReviews,
} from '../services/historyStorage';
import { isSupabaseConfigured } from '../services/supabase';
import { StatCard } from '../components/StatCard';
import { ReviewInput } from '../components/ReviewInput';
import { AnalysisResult } from '../components/AnalysisResult';
import { ReviewHistory } from '../components/ReviewHistory';
import { LoadingState } from '../components/LoadingState';

export const Dashboard: React.FC = () => {
  // Navigation tabs: 'dashboard' | 'analyze' | 'history' | 'analytics'
  const [activeTab, setActiveTab] = useState<'dashboard' | 'analyze' | 'history' | 'analytics'>('dashboard');

  // Review states
  const [currentAnalysis, setCurrentAnalysis] = useState<ReviewAnalysis | null>(null);
  const [activeReviewText, setActiveReviewText] = useState<string>('');
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // History state & storage source
  const [history, setHistory] = useState<ReviewHistoryItem[]>(() => getLocalReviews());
  const [storageSource, setStorageSource] = useState<'supabase' | 'local'>('local');
  const [isSyncing, setIsSyncing] = useState<boolean>(false);

  // Backend Health check status
  const [healthStatus, setHealthStatus] = useState<HealthStatus | null>(null);

  const analysisRef = useRef<HTMLDivElement>(null);

  // Load reviews from Supabase or LocalStorage on mount
  const refreshHistory = async () => {
    setIsSyncing(true);
    const { reviews, source } = await fetchAllReviews();
    setHistory(reviews);
    setStorageSource(source);
    setIsSyncing(false);
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

  // Compute live real statistics from history (no fake data)
  const stats: DashboardStats = useMemo(() => {
    if (history.length === 0) {
      return {
        totalReviews: 0,
        positiveReviews: 0,
        negativeReviews: 0,
        neutralReviews: 0,
        averageRating: 0,
      };
    }

    let positiveCount = 0;
    let negativeCount = 0;
    let neutralCount = 0;
    let totalRatingSum = 0;

    history.forEach((item) => {
      if (item.analysis.sentiment === 'positive') positiveCount++;
      else if (item.analysis.sentiment === 'negative') negativeCount++;
      else neutralCount++;

      totalRatingSum += item.analysis.rating;
    });

    const averageRating = Number((totalRatingSum / history.length).toFixed(1));

    return {
      totalReviews: history.length,
      positiveReviews: positiveCount,
      negativeReviews: negativeCount,
      neutralReviews: neutralCount,
      averageRating,
    };
  }, [history]);

  // Handle Review Analysis Submission
  const handleAnalyze = async (reviewText: string) => {
    setIsLoading(true);
    setErrorMessage(null);
    setActiveReviewText(reviewText);

    try {
      const analysis = await analyzeReview(reviewText);
      setCurrentAnalysis(analysis);

      // Save to Supabase & localStorage via unified service
      const newItem = await saveReviewAnalysis(reviewText, analysis);
      setHistory((prev) => [newItem, ...prev.filter((i) => i.id !== newItem.id)]);

      // Smooth scroll to analysis result
      setTimeout(() => {
        analysisRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }, 100);
    } catch (err: any) {
      setErrorMessage(err.message || 'An error occurred while analyzing the review.');
    } finally {
      setIsLoading(false);
    }
  };

  // History handlers
  const handleDeleteReview = async (id: string) => {
    await deleteReviewById(id);
    setHistory((prev) => prev.filter((item) => item.id !== id));
  };

  const handleClearHistory = async () => {
    await clearAllReviews();
    setHistory([]);
  };

  const handleSelectHistoryItem = (item: ReviewHistoryItem) => {
    setCurrentAnalysis(item.analysis);
    setActiveReviewText(item.reviewText);
    setActiveTab('dashboard');
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
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3.5 sm:px-6 lg:px-8">
          {/* Brand Logo & Title */}
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-tr from-purple-600 via-indigo-500 to-cyan-400 p-0.5 shadow-glow-purple">
              <div className="flex h-full w-full items-center justify-center rounded-[10px] bg-[#0B0F17]">
                <Sparkles className="h-5 w-5 text-purple-400" />
              </div>
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-base sm:text-lg font-extrabold tracking-wider text-white uppercase font-mono">
                  PRODUCT REVIEW ANALYZER
                </h1>
                <span className="rounded bg-purple-500/20 border border-purple-500/30 px-1.5 py-0.5 text-[10px] font-semibold text-purple-300">
                  AI v1.1
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
                Turn customer feedback into actionable insights with AI.
              </p>
            </div>
          </div>

          {/* Navigation Tabs */}
          <nav className="flex items-center gap-1 rounded-xl border border-slate-800 bg-[#111827]/80 p-1">
            <button
              onClick={() => setActiveTab('dashboard')}
              className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold transition ${
                activeTab === 'dashboard'
                  ? 'bg-purple-600 text-white shadow-sm'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Layers className="h-3.5 w-3.5" />
              <span>Dashboard</span>
            </button>
            <button
              onClick={() => setActiveTab('analyze')}
              className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold transition ${
                activeTab === 'analyze'
                  ? 'bg-purple-600 text-white shadow-sm'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <MessageSquare className="h-3.5 w-3.5" />
              <span>Analyze Review</span>
            </button>
            <button
              onClick={() => setActiveTab('history')}
              className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold transition ${
                activeTab === 'history'
                  ? 'bg-purple-600 text-white shadow-sm'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Activity className="h-3.5 w-3.5" />
              <span>History ({history.length})</span>
            </button>
            <button
              onClick={() => setActiveTab('analytics')}
              className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold transition ${
                activeTab === 'analytics'
                  ? 'bg-purple-600 text-white shadow-sm'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <BarChart3 className="h-3.5 w-3.5" />
              <span>Analytics</span>
            </button>
          </nav>
        </div>
      </header>

      {/* Main Container */}
      <main className="mx-auto max-w-7xl px-4 pt-6 sm:px-6 lg:px-8 space-y-8">
        {/* Backend Status Banner */}
        {healthStatus && healthStatus.status === 'offline' && (
          <div className="flex items-center gap-3 rounded-xl border border-rose-500/30 bg-rose-500/10 p-3.5 text-rose-300 text-xs">
            <AlertCircle className="h-4 w-4 shrink-0 text-rose-400" />
            <div className="flex-1">
              <strong>Backend Offline:</strong> Cannot connect to FastAPI backend at <code className="font-mono bg-rose-950/60 px-1 py-0.5 rounded">{API_BASE_URL}</code>. Please ensure the server is running.
            </div>
          </div>
        )}
        {healthStatus && healthStatus.status === 'ok' && !healthStatus.ai_configured && (
          <div className="flex items-center gap-3 rounded-xl border border-amber-500/30 bg-amber-500/10 p-3.5 text-amber-300 text-xs">
            <AlertCircle className="h-4 w-4 shrink-0 text-amber-400" />
            <div className="flex-1">
              <strong>Missing API Key:</strong> Gemini API key is not configured in <code className="font-mono bg-amber-950/60 px-1 py-0.5 rounded">backend/.env</code>. Analysis will fail until set.
            </div>
          </div>
        )}

        {/* Dashboard Section 1: Dynamic Live Statistics */}
        {(activeTab === 'dashboard' || activeTab === 'analytics') && (
          <section className="space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-bold uppercase tracking-wider text-slate-400 font-mono flex items-center gap-2">
                <BarChart3 className="h-4 w-4 text-purple-400" />
                Live Review Analytics
              </h2>
              <div className="flex items-center gap-3">
                {history.length > 0 && (
                  <span className="text-xs text-slate-400 font-medium">
                    Based on {history.length} verified analysis record{history.length === 1 ? '' : 's'}
                  </span>
                )}
                <button
                  onClick={refreshHistory}
                  disabled={isSyncing}
                  className="inline-flex items-center gap-1 text-[11px] text-slate-400 hover:text-purple-400 transition"
                  title="Sync reviews from Supabase"
                >
                  <RefreshCw className={`h-3 w-3 ${isSyncing ? 'animate-spin text-purple-400' : ''}`} />
                  <span>Sync DB</span>
                </button>
              </div>
            </div>

            {history.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-slate-800 bg-[#111827]/40 p-6 text-center">
                <p className="text-sm font-semibold text-slate-300">No reviews analyzed yet.</p>
                <p className="mt-1 text-xs text-slate-400">
                  Analyze your first customer review below to generate live sentiment and rating statistics.
                </p>
              </div>
            ) : (
              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3.5">
                <StatCard
                  title="Total Reviews"
                  value={stats.totalReviews}
                  icon={Layers}
                  color="purple"
                  subtitle="Processed"
                />
                <StatCard
                  title="Positive"
                  value={stats.positiveReviews}
                  icon={ThumbsUp}
                  color="emerald"
                  subtitle={`${((stats.positiveReviews / stats.totalReviews) * 100).toFixed(0)}%`}
                />
                <StatCard
                  title="Negative"
                  value={stats.negativeReviews}
                  icon={ThumbsDown}
                  color="rose"
                  subtitle={`${((stats.negativeReviews / stats.totalReviews) * 100).toFixed(0)}%`}
                />
                <StatCard
                  title="Neutral"
                  value={stats.neutralReviews}
                  icon={MinusCircle}
                  color="amber"
                  subtitle={`${((stats.neutralReviews / stats.totalReviews) * 100).toFixed(0)}%`}
                />
                <StatCard
                  title="Avg Rating"
                  value={`${stats.averageRating} ⭐`}
                  icon={Star}
                  color="cyan"
                  subtitle="Out of 5.0"
                />
              </div>
            )}
          </section>
        )}

        {/* Analytics Deep Dive View (When Analytics Tab is selected) */}
        {activeTab === 'analytics' && history.length > 0 && (
          <section className="grid grid-cols-1 md:grid-cols-2 gap-5">
            {/* Sentiment breakdown card */}
            <div className="rounded-2xl border border-white/10 bg-[#111827]/80 p-5 backdrop-blur-xl">
              <h3 className="text-sm font-bold text-white mb-4 flex items-center gap-2">
                <BarChart3 className="h-4 w-4 text-purple-400" />
                Sentiment Distribution
              </h3>
              <div className="space-y-3">
                <div>
                  <div className="flex justify-between text-xs font-medium mb-1 text-emerald-400">
                    <span>Positive</span>
                    <span>{stats.positiveReviews} ({((stats.positiveReviews / stats.totalReviews) * 100).toFixed(0)}%)</span>
                  </div>
                  <div className="h-2 w-full rounded-full bg-slate-800 overflow-hidden">
                    <div
                      className="h-full bg-emerald-500 rounded-full transition-all duration-500"
                      style={{ width: `${(stats.positiveReviews / stats.totalReviews) * 100}%` }}
                    />
                  </div>
                </div>

                <div>
                  <div className="flex justify-between text-xs font-medium mb-1 text-amber-400">
                    <span>Neutral</span>
                    <span>{stats.neutralReviews} ({((stats.neutralReviews / stats.totalReviews) * 100).toFixed(0)}%)</span>
                  </div>
                  <div className="h-2 w-full rounded-full bg-slate-800 overflow-hidden">
                    <div
                      className="h-full bg-amber-500 rounded-full transition-all duration-500"
                      style={{ width: `${(stats.neutralReviews / stats.totalReviews) * 100}%` }}
                    />
                  </div>
                </div>

                <div>
                  <div className="flex justify-between text-xs font-medium mb-1 text-rose-400">
                    <span>Negative</span>
                    <span>{stats.negativeReviews} ({((stats.negativeReviews / stats.totalReviews) * 100).toFixed(0)}%)</span>
                  </div>
                  <div className="h-2 w-full rounded-full bg-slate-800 overflow-hidden">
                    <div
                      className="h-full bg-rose-500 rounded-full transition-all duration-500"
                      style={{ width: `${(stats.negativeReviews / stats.totalReviews) * 100}%` }}
                    />
                  </div>
                </div>
              </div>
            </div>

            {/* Quality & Anti-Hallucination Guarantees */}
            <div className="rounded-2xl border border-white/10 bg-[#111827]/80 p-5 backdrop-blur-xl flex flex-col justify-between">
              <div>
                <h3 className="text-sm font-bold text-white mb-2 flex items-center gap-2">
                  <ShieldCheck className="h-4 w-4 text-cyan-400" />
                  Structured AI Extraction Engine
                </h3>
                <p className="text-xs text-slate-400 leading-relaxed">
                  Every review analysis executes with strict Pydantic model schemas over Google Gemini API, ensuring zero hallucinated features and 100% compliant JSON responses.
                </p>
              </div>

              <div className="mt-4 grid grid-cols-2 gap-3 pt-3 border-t border-slate-800 text-xs">
                <div className="flex items-center gap-2 text-slate-300">
                  <CheckCircle className="h-3.5 w-3.5 text-emerald-400" />
                  <span>Strict Rating (1-5)</span>
                </div>
                <div className="flex items-center gap-2 text-slate-300">
                  <CheckCircle className="h-3.5 w-3.5 text-emerald-400" />
                  <span>Anti-Hallucination Guard</span>
                </div>
                <div className="flex items-center gap-2 text-slate-300">
                  <CheckCircle className="h-3.5 w-3.5 text-emerald-400" />
                  <span>Evidence-only Pros/Cons</span>
                </div>
                <div className="flex items-center gap-2 text-slate-300">
                  <CheckCircle className="h-3.5 w-3.5 text-emerald-400" />
                  <span>Supabase Cloud Sync</span>
                </div>
              </div>
            </div>
          </section>
        )}

        {/* Dashboard Section 2: Review Input */}
        {(activeTab === 'dashboard' || activeTab === 'analyze') && (
          <section className="space-y-6">
            <ReviewInput
              onAnalyze={handleAnalyze}
              isLoading={isLoading}
              errorMessage={errorMessage}
              onClearError={() => setErrorMessage(null)}
            />

            {/* Loading Indicator */}
            {isLoading && <LoadingState message="Analyzing review with Gemini AI..." />}

            {/* Current Analysis Result */}
            {currentAnalysis && !isLoading && (
              <div ref={analysisRef} className="space-y-3">
                <div className="flex items-center justify-between">
                  <h3 className="text-xs font-semibold uppercase tracking-wider text-purple-400 font-mono flex items-center gap-1.5">
                    <Sparkles className="h-3.5 w-3.5" />
                    Latest Analysis Result
                  </h3>
                </div>
                <AnalysisResult
                  analysis={currentAnalysis}
                  originalText={activeReviewText}
                />
              </div>
            )}
          </section>
        )}

        {/* Dashboard Section 3: History */}
        {(activeTab === 'dashboard' || activeTab === 'history') && (
          <section>
            <ReviewHistory
              history={history}
              onSelectReview={handleSelectHistoryItem}
              onDeleteReview={handleDeleteReview}
              onClearHistory={handleClearHistory}
            />
          </section>
        )}
      </main>

      {/* Footer */}
      <footer className="mt-16 border-t border-slate-800/80 pt-8 text-center text-xs text-slate-400">
        <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
          <span>Product Review Analyzer • AI-Powered Feedback Intelligence</span>
          <span className="hidden sm:inline text-slate-700">•</span>
          <span>FastAPI + Pydantic + Google Gemini + Supabase + React</span>
        </div>
      </footer>
    </div>
  );
};
