import React, { useEffect, useState } from 'react';
import {
  Package,
  Search,
  Star,
  Sparkles,
} from 'lucide-react';
import { ProductAnalytics as ProductItem } from '../types/review';
import { getProducts } from '../services/api';

export const ProductAnalytics: React.FC = () => {
  const [products, setProducts] = useState<ProductItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string>('');
  const [search, setSearch] = useState<string>('');

  useEffect(() => {
    let isMounted = true;
    setLoading(true);
    getProducts(100)
      .then((data) => {
        if (isMounted) {
          setProducts(data);
          setError('');
        }
      })
      .catch((err) => {
        if (isMounted) {
          setError(
            err.response?.data?.detail || 'Failed to load product analytics from backend.'
          );
        }
      })
      .finally(() => {
        if (isMounted) setLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, []);

  const filtered = products.filter((p) => {
    const term = search.toLowerCase().trim();
    if (!term) return true;
    const asin = (p.asin || '').toLowerCase();
    const name = (p.product_name || '').toLowerCase();
    return asin.includes(term) || name.includes(term);
  });

  return (
    <div className="relative overflow-hidden rounded-2xl border border-white/10 bg-[#111827]/80 p-6 backdrop-blur-xl shadow-glass space-y-5">
      {/* Section Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800 pb-5">
        <div>
          <h2 className="text-lg font-bold text-white flex items-center gap-2">
            <Package className="h-5 w-5 text-indigo-400" />
            Product-Level Intelligence
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Aggregated metrics for individual ASINs ({products.length} distinct products found in dataset).
          </p>
        </div>

        {/* Search */}
        <div className="relative min-w-[220px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-slate-400" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search Product ID / ASIN..."
            className="w-full rounded-xl border border-slate-700 bg-[#0B0F17] py-2 pl-9 pr-3 text-xs text-slate-200 placeholder-slate-500 focus:border-indigo-500 focus:outline-none"
          />
        </div>
      </div>

      {loading ? (
        <div className="py-12 text-center space-y-3">
          <div className="inline-block h-8 w-8 animate-spin rounded-full border-2 border-indigo-400 border-t-transparent" />
          <p className="text-xs text-slate-400 font-mono">Aggregating product analytics...</p>
        </div>
      ) : error ? (
        <div className="rounded-xl border border-rose-500/30 bg-rose-500/10 p-5 text-center text-xs text-rose-300">
          <p className="font-semibold">{error}</p>
        </div>
      ) : filtered.length === 0 ? (
        <div className="rounded-xl border border-dashed border-slate-800 p-8 text-center text-xs text-slate-400">
          No products match your search.
        </div>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-slate-800 bg-[#0B0F17]/90">
          <table className="w-full text-left text-xs">
            <thead className="border-b border-slate-800 bg-slate-900/60 text-slate-400 font-mono uppercase text-[10px]">
              <tr>
                <th className="p-3">Product ID (ASIN)</th>
                <th className="p-3 text-center">Reviews</th>
                <th className="p-3 text-center">Actual Avg Rating</th>
                <th className="p-3 text-center">AI Predicted Avg</th>
                <th className="p-3">Sentiment Breakdown</th>
                <th className="p-3 text-right">Helpful Votes</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {filtered.map((item, idx) => (
                <tr key={item.asin || idx} className="hover:bg-slate-800/30 transition">
                  {/* ASIN */}
                  <td className="p-3">
                    <div className="font-mono font-bold text-cyan-300">
                      {item.product_name ? item.product_name : `Product ID: ${item.asin || '—'}`}
                    </div>
                    {!item.product_name && (
                      <span className="text-[10px] text-slate-500 block">
                        Verified ASIN (Standard Kaggle Identifier)
                      </span>
                    )}
                  </td>

                  {/* Review count */}
                  <td className="p-3 text-center font-mono font-semibold text-white">
                    {item.review_count.toLocaleString()}
                  </td>

                  {/* Actual Rating */}
                  <td className="p-3 text-center">
                    <span className="inline-flex items-center gap-1 font-mono font-bold text-amber-400 bg-amber-500/10 px-2 py-0.5 rounded border border-amber-500/20">
                      <Star className="h-3 w-3 fill-amber-400" />
                      {item.average_actual_rating}
                    </span>
                  </td>

                  {/* AI Predicted Rating */}
                  <td className="p-3 text-center font-mono">
                    {item.average_ai_rating != null ? (
                      <span className="inline-flex items-center gap-1 font-bold text-purple-400 bg-purple-500/10 px-2 py-0.5 rounded border border-purple-500/20">
                        <Sparkles className="h-3 w-3" />
                        {item.average_ai_rating}
                      </span>
                    ) : (
                      <span className="text-slate-500 text-[11px] italic">
                        Not evaluated yet
                      </span>
                    )}
                  </td>

                  {/* Sentiment Breakdown */}
                  <td className="p-3 min-w-[180px]">
                    <div className="flex items-center gap-2 text-[11px] font-mono">
                      <span className="text-emerald-400" title="Positive">
                        +{item.positive_reviews}
                      </span>
                      <span className="text-slate-600">/</span>
                      <span className="text-amber-400" title="Neutral">
                        ~{item.neutral_reviews}
                      </span>
                      <span className="text-slate-600">/</span>
                      <span className="text-rose-400" title="Negative">
                        -{item.negative_reviews}
                      </span>
                    </div>
                    {/* Small progress bar */}
                    <div className="h-1.5 w-full rounded-full bg-slate-800 flex overflow-hidden mt-1">
                      <div
                        className="bg-emerald-500"
                        style={{
                          width: `${(item.positive_reviews / item.review_count) * 100}%`,
                        }}
                      />
                      <div
                        className="bg-amber-500"
                        style={{
                          width: `${(item.neutral_reviews / item.review_count) * 100}%`,
                        }}
                      />
                      <div
                        className="bg-rose-500"
                        style={{
                          width: `${(item.negative_reviews / item.review_count) * 100}%`,
                        }}
                      />
                    </div>
                  </td>

                  {/* Helpful votes */}
                  <td className="p-3 text-right font-mono text-slate-300">
                    {item.helpful_votes.toLocaleString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};
