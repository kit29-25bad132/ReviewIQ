import React, { useEffect, useState } from 'react';
import {
  searchProducts,
  getProductAnalysis,
  getProductReviews,
  generateAISummary,
} from '../services/api';
import type {
  ProductSummary,
  ProductAnalysisResponse,
  ReviewsPaginationResponse,
  AISummaryResponse,
} from '../types/ecommerce';

export const ProductInsights: React.FC = () => {
  const [query, setQuery] = useState('');
  const [products, setProducts] = useState<ProductSummary[]>([]);
  const [selected, setSelected] = useState<ProductAnalysisResponse | null>(null);
  const [reviews, setReviews] = useState<ReviewsPaginationResponse | null>(null);
  const [summary, setSummary] = useState<AISummaryResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!query.trim()) {
      setProducts([]);
      return;
    }

    const timer = setTimeout(async () => {
      try {
        const result = await searchProducts(query);
        setProducts(result.products);
      } catch {
        setProducts([]);
      }
    }, 350);

    return () => clearTimeout(timer);
  }, [query]);

  const selectProduct = async (product: ProductSummary) => {
    setQuery(product.product_title);
    setProducts([]);
    setLoading(true);
    setError('');
    setSummary(null);

    try {
      const [analysis, reviewData] = await Promise.all([
        getProductAnalysis(product.product_id),
        getProductReviews(product.product_id, { page: 1, limit: 10 }),
      ]);

      setSelected(analysis);
      setReviews(reviewData);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load product.');
    } finally {
      setLoading(false);
    }
  };

  const loadAISummary = async () => {
    if (!selected) return;

    setSummaryLoading(true);
    try {
      const result = await generateAISummary(selected.product.product_id);
      setSummary(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'AI summary failed.');
    } finally {
      setSummaryLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#0E0F10] text-[#F5F2EA]">
      <header className="border-b border-[#292A2B] px-6 py-5">
        <div className="mx-auto max-w-6xl">
          <p className="text-xs uppercase tracking-[0.25em] text-[#D4AF5A]">
            ReviewIQ
          </p>
          <h1 className="mt-2 text-3xl font-medium">
            Product Review Intelligence
          </h1>
          <p className="mt-2 text-sm text-[#AAA79F]">
            Search products and explore intelligence from real customer reviews.
          </p>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-6 py-8">
        <div className="relative">
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search for a product..."
            className="w-full rounded-xl border border-[#292A2B] bg-[#151617] px-5 py-4 text-sm text-[#F5F2EA] placeholder:text-[#74736E]"
          />

          {products.length > 0 && (
            <div className="absolute z-10 mt-2 w-full overflow-hidden rounded-xl border border-[#292A2B] bg-[#151617] shadow-2xl">
              {products.map((product) => (
                <button
                  key={product.product_id}
                  onClick={() => selectProduct(product)}
                  className="flex w-full items-center justify-between border-b border-[#292A2B] px-5 py-4 text-left hover:bg-[#1C1D1F]"
                >
                  <div>
                    <p className="text-sm font-medium">{product.product_title}</p>
                    <p className="mt-1 text-xs text-[#74736E]">
                      {product.category || 'Product'} · {product.review_count} reviews
                    </p>
                  </div>
                  <span className="text-sm text-[#D4AF5A]">
                    {product.average_rating.toFixed(1)}/5
                  </span>
                </button>
              ))}
            </div>
          )}
        </div>

        {loading && (
          <p className="mt-8 text-sm text-[#AAA79F]">Loading product intelligence...</p>
        )}

        {error && (
          <div className="mt-6 rounded-xl border border-red-900/40 bg-red-950/20 p-4 text-sm text-red-300">
            {error}
          </div>
        )}

        {selected && !loading && (
          <div className="mt-8 space-y-6">
            <section className="premium-panel p-6">
              <p className="text-xs uppercase tracking-[0.2em] text-[#D4AF5A]">
                {selected.product.category || 'Product'}
              </p>

              <div className="mt-3 flex flex-col justify-between gap-5 md:flex-row md:items-end">
                <div>
                  <h2 className="text-3xl font-medium">
                    {selected.product.product_title}
                  </h2>
                  <p className="mt-2 text-sm text-[#74736E]">
                    {selected.statistics.review_count} customer reviews analyzed
                  </p>
                </div>

                <div className="text-right">
                  <div className="text-4xl font-semibold text-[#D4AF5A]">
                    {selected.statistics.average_rating.toFixed(1)}
                  </div>
                  <p className="text-xs text-[#74736E]">Overall rating / 5</p>
                </div>
              </div>
            </section>

            <section className="grid gap-4 md:grid-cols-2">
              <div className="premium-panel p-5">
                <h3 className="text-sm font-medium">Rating Distribution</h3>
                <div className="mt-4 space-y-3">
                  {[5, 4, 3, 2, 1].map((rating) => {
                    const count =
                      selected.statistics.rating_distribution[String(rating)] || 0;

                    return (
                      <div key={rating} className="flex items-center gap-3 text-sm">
                        <span className="w-8 text-[#AAA79F]">{rating}★</span>
                        <div className="h-2 flex-1 rounded-full bg-[#292A2B]">
                          <div
                            className="h-2 rounded-full bg-[#D4AF5A]"
                            style={{
                              width: `${
                                selected.statistics.review_count
                                  ? (count / selected.statistics.review_count) * 100
                                  : 0
                              }%`,
                            }}
                          />
                        </div>
                        <span className="w-10 text-right text-[#74736E]">
                          {count}
                        </span>
                      </div>
                    );
                  })}
                </div>
              </div>

              <div className="premium-panel p-5">
                <h3 className="text-sm font-medium">Sentiment Distribution</h3>
                <div className="mt-4 space-y-4">
                  {Object.entries(selected.statistics.sentiment_distribution).map(
                    ([sentiment, count]) => (
                      <div
                        key={sentiment}
                        className="flex items-center justify-between border-b border-[#292A2B] pb-3"
                      >
                        <span className="capitalize text-[#AAA79F]">{sentiment}</span>
                        <span className="text-[#D4AF5A]">{count}</span>
                      </div>
                    )
                  )}
                </div>
              </div>
            </section>

            <section className="premium-panel p-6">
              <div className="flex items-center justify-between gap-4">
                <h3 className="text-lg font-medium">AI Review Summary</h3>
                <button
                  onClick={loadAISummary}
                  disabled={summaryLoading}
                  className="gold-button px-4 py-2 text-sm disabled:opacity-50"
                >
                  {summaryLoading ? 'Analyzing...' : 'Generate Summary'}
                </button>
              </div>

              {summary && (
                <div className="mt-5">
                  <p className="text-sm leading-7 text-[#AAA79F]">{summary.summary}</p>

                  <div className="mt-6 grid gap-5 md:grid-cols-2">
                    <div>
                      <p className="text-xs uppercase tracking-wider text-[#D4AF5A]">
                        Common Pros
                      </p>
                      <ul className="mt-3 space-y-2 text-sm text-[#AAA79F]">
                        {summary.common_pros.map((item) => (
                          <li key={item}>+ {item}</li>
                        ))}
                      </ul>
                    </div>

                    <div>
                      <p className="text-xs uppercase tracking-wider text-[#D4AF5A]">
                        Common Cons
                      </p>
                      <ul className="mt-3 space-y-2 text-sm text-[#AAA79F]">
                        {summary.common_cons.map((item) => (
                          <li key={item}>− {item}</li>
                        ))}
                      </ul>
                    </div>
                  </div>
                </div>
              )}
            </section>

            <section className="premium-panel p-6">
              <h3 className="text-lg font-medium">Recent Customer Reviews</h3>

              <div className="mt-5 space-y-4">
                {reviews?.items.map((review) => (
                  <article
                    key={review.id}
                    className="border-b border-[#292A2B] pb-4 last:border-0"
                  >
                    <div className="flex items-center justify-between gap-4">
                      <span className="text-[#D4AF5A]">
                        {'★'.repeat(review.rating)}
                      </span>
                      <span className="text-xs capitalize text-[#74736E]">
                        {review.sentiment}
                      </span>
                    </div>
                    <p className="mt-2 text-sm leading-6 text-[#AAA79F]">
                      {review.review_text}
                    </p>
                  </article>
                ))}
              </div>
            </section>
          </div>
        )}
      </main>
    </div>
  );
};

export default ProductInsights;