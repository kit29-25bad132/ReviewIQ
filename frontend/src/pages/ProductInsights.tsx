import React, { useEffect, useState } from 'react';
import {
  ArrowLeft,
  Package,
  Database,
  AlertCircle,
} from 'lucide-react';
import {
  getProductAnalysis,
  getOverview,
  getProducts,
} from '../services/api';
import type {
  ProductSummary,
  ProductAnalysisResponse,
} from '../types/ecommerce';
import type { OverviewAnalytics, ProductAnalytics } from '../types/review';
import { ProductSearch } from '../components/ProductSearch';
import { ProductOverview } from '../components/ProductOverview';
import { ProsConsAnalysis } from '../components/ProsConsAnalysis';
import { PersonalizedRecommendation } from '../components/PersonalizedRecommendation';
import { AISummaryCard } from '../components/AISummaryCard';
import { ReviewList } from '../components/ReviewList';

interface ProductInsightsProps {
  onBack?: () => void;
  initialProductId?: string;
}

export const ProductInsights: React.FC<ProductInsightsProps> = ({
  onBack,
  initialProductId,
}) => {
  const [selectedProduct, setSelectedProduct] = useState<ProductSummary | null>(null);
  const [analysis, setAnalysis] = useState<ProductAnalysisResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string>('');

  // Overview analytics tab
  const [activeSubTab, setActiveSubTab] = useState<'product' | 'dataset'>('product');
  const [overviewData, setOverviewData] = useState<OverviewAnalytics | null>(null);
  const [datasetProducts, setDatasetProducts] = useState<ProductAnalytics[]>([]);
  const [loadingDataset, setLoadingDataset] = useState<boolean>(false);

  const loadProduct = async (product: ProductSummary) => {
    setSelectedProduct(product);
    setLoading(true);
    setError('');
    try {
      const res = await getProductAnalysis(product.product_id);
      setAnalysis(res);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load product analytics.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (initialProductId) {
      loadProduct({
        product_id: initialProductId,
        product_title: 'Loading Product...',
        category: 'Product',
        review_count: 0,
        average_rating: 0,
      });
    } else {
      // Default to Electric Toothbrush
      loadProduct({
        product_id: '9640962',
        product_title: 'Electric Toothbrush',
        category: 'Health & Personal Care',
        review_count: 11,
        average_rating: 3.64,
      });
    }
  }, [initialProductId]);

  const loadDatasetAnalytics = async () => {
    setLoadingDataset(true);
    try {
      const [ov, prods] = await Promise.all([getOverview(), getProducts(50)]);
      setOverviewData(ov);
      setDatasetProducts(prods);
    } catch {
      // Ignore if offline
    } finally {
      setLoadingDataset(false);
    }
  };

  useEffect(() => {
    if (activeSubTab === 'dataset' && !overviewData) {
      loadDatasetAnalytics();
    }
  }, [activeSubTab]);

  return (
    <div className="min-h-screen bg-[#0E0F10] text-[#F5F2EA] pb-24">
      {/* Top Header */}
      <header className="border-b border-[#292A2B]/80 bg-[#0E0F10]/95 backdrop-blur px-6 py-6 sm:px-8 lg:px-10">
        <div className="mx-auto flex max-w-[1280px] items-center justify-between">
          <div>
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-semibold uppercase tracking-[0.25em] text-[#D4AF5A]">
                ReviewIQ
              </span>
              <span className="text-[#74736E]">·</span>
              <span className="text-[10px] uppercase tracking-[0.18em] text-[#74736E]">
                Product Intelligence
              </span>
            </div>
            <h1 className="mt-1.5 text-2xl sm:text-3xl font-medium tracking-tight">
              Product Insights & Analytics
            </h1>
            <p className="mt-1 text-xs text-[#AAA79F]">
              Explore structured customer feedback, rating distributions, pros/cons, and category comparisons.
            </p>
          </div>

          {onBack && (
            <button
              onClick={onBack}
              className="inline-flex items-center gap-2 rounded-xl border border-[#292A2B] bg-[#151617] px-4 py-2 text-xs text-[#AAA79F] hover:border-[#D4AF5A]/30 hover:text-[#F5F2EA] transition"
            >
              <ArrowLeft className="h-3.5 w-3.5" />
              <span>Back to Home</span>
            </button>
          )}
        </div>
      </header>

      {/* Main Content Area */}
      <main className="mx-auto max-w-[1280px] px-6 sm:px-8 lg:px-10 pt-8 space-y-8">
        {/* Search Bar & Mode Selector */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex-1 max-w-2xl">
            <ProductSearch
              onSelectProduct={loadProduct}
              selectedProductId={selectedProduct?.product_id}
            />
          </div>

          {/* Sub-tab pills */}
          <div className="flex items-center gap-1 self-start rounded-xl border border-[#292A2B] bg-[#151617] p-1 shrink-0">
            <button
              onClick={() => setActiveSubTab('product')}
              className={`inline-flex items-center gap-1.5 rounded-lg px-4 py-2 text-xs font-semibold transition ${
                activeSubTab === 'product'
                  ? 'border border-[#D4AF5A]/50 bg-[#1B1915] text-[#F0D58A]'
                  : 'text-[#AAA79F] hover:text-[#F5F2EA]'
              }`}
            >
              <Package className="h-3.5 w-3.5" />
              <span>Product Intelligence</span>
            </button>
            <button
              onClick={() => setActiveSubTab('dataset')}
              className={`inline-flex items-center gap-1.5 rounded-lg px-4 py-2 text-xs font-semibold transition ${
                activeSubTab === 'dataset'
                  ? 'border border-[#D4AF5A]/50 bg-[#1B1915] text-[#F0D58A]'
                  : 'text-[#AAA79F] hover:text-[#F5F2EA]'
              }`}
            >
              <Database className="h-3.5 w-3.5" />
              <span>Dataset Overview</span>
            </button>
          </div>
        </div>

        {/* Tab 1: Product Specific Intelligence */}
        {activeSubTab === 'product' && (
          <div className="space-y-8">
            {loading && (
              <div className="premium-panel p-16 text-center space-y-3">
                <div className="inline-block h-6 w-6 animate-spin rounded-full border-2 border-[#D4AF5A] border-t-transparent" />
                <p className="text-xs text-[#AAA79F]">Retrieving product analytics and review data...</p>
              </div>
            )}

            {error && (
              <div className="rounded-xl border border-rose-900/40 bg-rose-950/20 p-5 text-xs text-rose-300 flex items-center gap-2">
                <AlertCircle className="h-4 w-4 shrink-0" />
                <span>{error}</span>
              </div>
            )}

            {analysis && !loading && (
              <div className="space-y-8 animate-fadeIn">
                {/* 1. Product Overview */}
                <ProductOverview analysis={analysis} />

                {/* 2. Pros & Cons Analysis with Evidence Citations */}
                <ProsConsAnalysis
                  productId={analysis.product.product_id}
                  productTitle={analysis.product.product_title}
                />

                {/* 3. AI Review Summary */}
                <AISummaryCard productId={analysis.product.product_id} />

                {/* 4. Related Products Comparison */}
                <PersonalizedRecommendation
                  productId={analysis.product.product_id}
                  productTitle={analysis.product.product_title}
                  onSelectAlternativeProduct={loadProduct}
                />

                {/* 5. Actual Customer Reviews with Filters and Pagination */}
                <ReviewList
                  productId={analysis.product.product_id}
                  productTitle={analysis.product.product_title}
                />
              </div>
            )}

            {!analysis && !loading && !error && (
              <div className="premium-panel p-16 text-center space-y-3">
                <Package className="h-8 w-8 text-[#74736E] mx-auto" />
                <h3 className="text-base font-medium text-[#F5F2EA]">No product selected</h3>
                <p className="text-xs text-[#74736E] max-w-sm mx-auto">
                  Use the search bar above or click one of the quick test chips to view real product intelligence.
                </p>
              </div>
            )}
          </div>
        )}

        {/* Tab 2: Dataset Analytics Overview */}
        {activeSubTab === 'dataset' && (
          <div className="space-y-8">
            {loadingDataset ? (
              <div className="premium-panel p-16 text-center space-y-3">
                <div className="inline-block h-6 w-6 animate-spin rounded-full border-2 border-[#D4AF5A] border-t-transparent" />
                <p className="text-xs text-[#AAA79F]">Calculating aggregate metrics across dataset...</p>
              </div>
            ) : overviewData ? (
              <div className="space-y-6">
                {/* Metric cards */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                  <div className="premium-panel p-5 space-y-1">
                    <p className="text-xs text-[#74736E]">Total Reviews</p>
                    <p className="text-2xl font-semibold text-[#F5F2EA]">
                      {overviewData.total_reviews.toLocaleString()}
                    </p>
                  </div>
                  <div className="premium-panel p-5 space-y-1">
                    <p className="text-xs text-[#74736E]">Average Rating</p>
                    <p className="text-2xl font-semibold text-[#D4AF5A]">
                      ★ {overviewData.average_rating.toFixed(2)}
                    </p>
                  </div>
                  <div className="premium-panel p-5 space-y-1">
                    <p className="text-xs text-[#74736E]">Positive Reviews</p>
                    <p className="text-2xl font-semibold text-emerald-400">
                      {overviewData.positive_reviews.toLocaleString()}
                    </p>
                  </div>
                  <div className="premium-panel p-5 space-y-1">
                    <p className="text-xs text-[#74736E]">Negative Reviews</p>
                    <p className="text-2xl font-semibold text-rose-400">
                      {overviewData.negative_reviews.toLocaleString()}
                    </p>
                  </div>
                </div>

                {/* Products Table */}
                {datasetProducts.length > 0 && (
                  <div className="premium-panel p-6 space-y-4">
                    <h3 className="text-sm font-medium text-[#F5F2EA]">
                      Aggregated Dataset Products
                    </h3>
                    <div className="overflow-x-auto">
                      <table className="w-full text-left text-xs border-collapse">
                        <thead>
                          <tr className="border-b border-[#292A2B] text-[#74736E]">
                            <th className="p-3">ASIN / Product</th>
                            <th className="p-3">Reviews</th>
                            <th className="p-3">Actual Rating</th>
                            <th className="p-3">Positive</th>
                            <th className="p-3">Negative</th>
                            <th className="p-3 text-right">Action</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-[#292A2B]/60">
                          {datasetProducts.map((p) => (
                            <tr key={p.asin} className="hover:bg-[#1C1D1F] transition">
                              <td className="p-3 font-medium text-[#F5F2EA]">{p.asin}</td>
                              <td className="p-3 font-mono text-[#AAA79F]">{p.review_count}</td>
                              <td className="p-3 text-[#D4AF5A] font-semibold">★ {p.average_actual_rating}</td>
                              <td className="p-3 text-emerald-400">{p.positive_reviews}</td>
                              <td className="p-3 text-rose-400">{p.negative_reviews}</td>
                              <td className="p-3 text-right">
                                <button
                                  onClick={() => {
                                    setActiveSubTab('product');
                                    loadProduct({
                                      product_id: p.asin || '',
                                      product_title: p.asin || 'Product',
                                      category: 'Dataset Product',
                                      review_count: p.review_count,
                                      average_rating: p.average_actual_rating,
                                    });
                                  }}
                                  className="rounded-lg border border-[#292A2B] bg-[#151617] px-2.5 py-1 text-[11px] font-medium text-[#D4AF5A] hover:border-[#D4AF5A]/40 transition"
                                >
                                  Inspect
                                </button>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="premium-panel p-12 text-center text-xs text-[#74736E]">
                Dataset overview analytics unavailable.
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
};