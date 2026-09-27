import React, { useEffect, useState, useRef } from 'react';
import {
  getProductAnalysis,
  getProductProsCons,
  generateAISummary,
} from '../services/api';
import { ProductSummary, ProductAnalysisResponse, ProsConsAnalysisResponse, AISummaryResponse } from '../types/ecommerce';
import { ProductHeader } from '../components/ProductHeader';
import { AISummaryCard } from '../components/AISummaryCard';
import { SentimentOverview } from '../components/SentimentOverview';
import { AspectInsightsCard } from '../components/AspectInsightsCard';
import { ProsConsSection } from '../components/ProsConsSection';
import { EvidenceViewer } from '../components/EvidenceViewer';
import { CustomerReviewsTable } from '../components/CustomerReviewsTable';
import { ProcessingScreen } from '../components/ProcessingScreen';
import { ErrorState } from '../components/ErrorState';
import { saveProductToHistory } from '../services/historyStorage';

interface DashboardPageProps {
  productId: string;
  initialProduct?: ProductSummary | null;
  onBackToSearch: () => void;
}

export const DashboardPage: React.FC<DashboardPageProps> = ({
  productId,
  initialProduct,
  onBackToSearch,
}) => {
  const [analysisData, setAnalysisData] = useState<ProductAnalysisResponse | null>(null);
  const [prosConsData, setProsConsData] = useState<ProsConsAnalysisResponse | null>(null);
  const [aiSummaryData, setAiSummaryData] = useState<AISummaryResponse | null>(null);

  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [errorType, setErrorType] = useState<'notFound' | 'offline' | 'timeout' | 'empty' | 'generic' | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Evidence tracing state
  const [selectedTheme, setSelectedTheme] = useState<string | null>(null);
  const [selectedSentiment, setSelectedSentiment] = useState<'positive' | 'negative' | null>(null);

  const evidenceRef = useRef<HTMLDivElement>(null);

  const loadProductIntelligence = async (isRefresh: boolean = false) => {
    if (isRefresh) {
      setIsRefreshing(true);
    } else {
      setIsLoading(true);
    }
    setErrorType(null);
    setErrorMessage(null);

    try {
      // Step 1: Fetch core product analysis and statistical distributions
      const analysis = await getProductAnalysis(productId);
      setAnalysisData(analysis);

      // Save to recent product history
      saveProductToHistory({
        productId: analysis.product.product_id,
        productTitle: analysis.product.product_title,
        category: analysis.product.category,
        overallRating: analysis.statistics.average_rating,
        reviewCount: analysis.statistics.review_count,
      });

      // Step 2: Concurrently fetch dynamic pros & cons
      try {
        const prosCons = await getProductProsCons(productId);
        setProsConsData(prosCons);
      } catch (pcErr) {
        console.warn('Pros/Cons generation deferred or failed:', pcErr);
      }

      // Step 3: Concurrently fetch grounded AI summary
      try {
        const aiSummary = await generateAISummary(productId);
        setAiSummaryData(aiSummary);
      } catch (aiErr) {
        console.warn('AI summary generation deferred or failed:', aiErr);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to retrieve product intelligence.';
      setErrorMessage(msg);

      if (msg.toLowerCase().includes('not found') || msg.includes('404')) {
        setErrorType('notFound');
      } else if (msg.toLowerCase().includes('offline') || msg.toLowerCase().includes('unavailable')) {
        setErrorType('offline');
      } else if (msg.toLowerCase().includes('timed out') || msg.toLowerCase().includes('timeout')) {
        setErrorType('timeout');
      } else {
        setErrorType('generic');
      }
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  };

  useEffect(() => {
    loadProductIntelligence(false);
  }, [productId]);

  const handleSelectThemeForEvidence = (theme: string, sentiment: 'positive' | 'negative') => {
    setSelectedTheme(theme);
    setSelectedSentiment(sentiment);

    // Smooth scroll down to evidence viewer
    if (evidenceRef.current) {
      evidenceRef.current.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  };

  const handleClearTheme = () => {
    setSelectedTheme(null);
    setSelectedSentiment(null);
  };

  if (isLoading) {
    return (
      <ProcessingScreen
        productTitle={initialProduct?.product_title}
        onCancel={onBackToSearch}
      />
    );
  }

  if (errorType || !analysisData) {
    return (
      <div className="py-12 px-4">
        <ErrorState
          type={errorType || 'generic'}
          message={errorMessage || undefined}
          onRetry={() => loadProductIntelligence(false)}
          onBack={onBackToSearch}
        />
      </div>
    );
  }

  const { product, statistics, recent_reviews } = analysisData;

  return (
    <div className="min-h-screen pb-20">
      {/* Product Header */}
      <ProductHeader
        product={product}
        statistics={statistics}
        onBack={onBackToSearch}
        onRefresh={() => loadProductIntelligence(true)}
        isRefreshing={isRefreshing}
      />

      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 pt-8 space-y-8">
        {/* AI Executive Summary */}
        <section>
          <AISummaryCard
            summaryData={aiSummaryData}
            fallbackSummary={prosConsData?.summary}
          />
        </section>

        {/* Sentiment & Rating Overview */}
        <section>
          <SentimentOverview
            statistics={statistics}
            sentimentPercentages={prosConsData?.sentiment_percentages}
          />
        </section>

        {/* Dynamic Aspect-Based Insights */}
        <section>
          <AspectInsightsCard
            pros={prosConsData?.pros || []}
            cons={prosConsData?.cons || []}
            totalAnalyzedReviews={statistics.review_count}
            onSelectThemeForEvidence={handleSelectThemeForEvidence}
            selectedTheme={selectedTheme}
          />
        </section>

        {/* Quantified Pros & Cons */}
        <section>
          <ProsConsSection
            pros={prosConsData?.pros || []}
            cons={prosConsData?.cons || []}
            authenticitySignals={prosConsData?.authenticity_signals}
            onSelectTheme={handleSelectThemeForEvidence}
            selectedTheme={selectedTheme}
          />
        </section>

        {/* Traceable Review Evidence (anchored ref for smooth scroll) */}
        <section ref={evidenceRef}>
          <EvidenceViewer
            productId={product.product_id}
            selectedTheme={selectedTheme}
            selectedSentiment={selectedSentiment}
            initialReviews={recent_reviews}
            onClearTheme={handleClearTheme}
          />
        </section>

        {/* Customer Reviews Explorer */}
        <section>
          <CustomerReviewsTable
            productId={product.product_id}
            initialReviews={recent_reviews}
          />
        </section>
      </div>
    </div>
  );
};
