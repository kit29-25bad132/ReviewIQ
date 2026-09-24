import React, { useState, useEffect, useRef } from 'react';
import { Search, Sparkles, XCircle, Package, ArrowRight, AlertCircle, Layers } from 'lucide-react';
import { ProductSummary } from '../types/ecommerce';
import { searchProducts } from '../services/api';

interface ProductSearchProps {
  onSelectProduct: (product: ProductSummary) => void;
  selectedProductId?: string;
}

const SAMPLE_PRODUCTS = [
  'Electric Toothbrush',
  'Stainless Steel Blender',
  'LEGO Building Kit',
  'Smartwatch Fitness Tracker',
  'Noise-Canceling Headphones',
  'Hydrating Facial Serum',
];

export const ProductSearch: React.FC<ProductSearchProps> = ({
  onSelectProduct,
  selectedProductId,
}) => {
  const [query, setQuery] = useState<string>('');
  const [suggestions, setSuggestions] = useState<ProductSummary[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [isOpen, setIsOpen] = useState<boolean>(false);
  const [notFoundMessage, setNotFoundMessage] = useState<string | null>(null);
  const wrapperRef = useRef<HTMLDivElement>(null);

  // Debounced search for suggestions
  useEffect(() => {
    if (!query.trim()) {
      setSuggestions([]);
      setNotFoundMessage(null);
      setLoading(false);
      return;
    }

    const timer = setTimeout(async () => {
      setLoading(true);
      setNotFoundMessage(null);
      try {
        const res = await searchProducts(query, 8);
        if (res.found && res.products.length > 0) {
          setSuggestions(res.products);
          setNotFoundMessage(null);
        } else {
          setSuggestions([]);
          setNotFoundMessage(res.message || 'Product not found in the available review dataset.');
        }
      } catch {
        setSuggestions([]);
        setNotFoundMessage('Failed to query review dataset.');
      } finally {
        setLoading(false);
      }
    }, 250);

    return () => clearTimeout(timer);
  }, [query]);

  // Click outside listener
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleSelect = (product: ProductSummary) => {
    setQuery(product.product_title);
    setIsOpen(false);
    onSelectProduct(product);
  };

  const handleQuickChip = (title: string) => {
    setQuery(title);
    setIsOpen(true);
  };

  const handleClear = () => {
    setQuery('');
    setSuggestions([]);
    setNotFoundMessage(null);
    setIsOpen(false);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (suggestions.length > 0) {
      handleSelect(suggestions[0]);
    }
  };

  return (
    <div ref={wrapperRef} className="relative w-full space-y-3">
      {/* Search Input Box */}
      <form onSubmit={handleSubmit} className="relative">
        <div className="relative flex items-center">
          <Search className="absolute left-4 h-5 w-5 text-purple-400 pointer-events-none" />
          <input
            type="text"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setIsOpen(true);
            }}
            onFocus={() => setIsOpen(true)}
            placeholder="Search product name... (e.g. Electric Toothbrush, LEGO Building Kit)"
            className="w-full rounded-2xl border border-purple-500/30 bg-[#0B0F17]/90 py-4 pl-12 pr-28 text-sm sm:text-base text-white placeholder-slate-500 shadow-glass backdrop-blur-xl focus:border-purple-400 focus:outline-none focus:ring-2 focus:ring-purple-500/20 transition duration-200"
          />

          <div className="absolute right-3 flex items-center gap-2">
            {query && (
              <button
                type="button"
                onClick={handleClear}
                className="p-1 text-slate-400 hover:text-white transition"
                title="Clear input"
              >
                <XCircle className="h-4 w-4" />
              </button>
            )}
            <button
              type="submit"
              disabled={loading || !query.trim()}
              className="inline-flex items-center gap-1.5 rounded-xl bg-gradient-to-r from-purple-600 via-indigo-600 to-cyan-500 px-4 py-2 text-xs font-semibold text-white shadow-md hover:brightness-110 disabled:opacity-40 transition"
            >
              {loading ? (
                <div className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-white border-t-transparent" />
              ) : (
                <Sparkles className="h-3.5 w-3.5" />
              )}
              <span>Analyze</span>
            </button>
          </div>
        </div>
      </form>

      {/* Quick Search Suggestions Chips */}
      <div className="flex flex-wrap items-center gap-2 pt-1 text-xs">
        <span className="text-slate-500 font-mono flex items-center gap-1">
          <Layers className="h-3 w-3" /> Quick Test:
        </span>
        {SAMPLE_PRODUCTS.map((p) => (
          <button
            key={p}
            type="button"
            onClick={() => handleQuickChip(p)}
            className="rounded-lg border border-slate-800 bg-[#111827]/80 px-2.5 py-1 text-slate-300 hover:border-purple-500/40 hover:bg-purple-500/10 hover:text-purple-300 transition"
          >
            {p}
          </button>
        ))}
      </div>

      {/* Autocomplete Dropdown */}
      {isOpen && query.trim() && (
        <div className="absolute left-0 right-0 top-14 z-50 overflow-hidden rounded-2xl border border-purple-500/30 bg-[#0B0F17] shadow-2xl backdrop-blur-xl animate-fadeIn">
          {loading ? (
            <div className="p-4 text-center text-xs text-slate-400 space-y-2">
              <div className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-purple-400 border-t-transparent" />
              <p>Searching 4,000,000 dataset records...</p>
            </div>
          ) : notFoundMessage ? (
            <div className="p-5 text-center text-xs text-rose-300 flex items-center justify-center gap-2">
              <AlertCircle className="h-4 w-4 text-rose-400 shrink-0" />
              <span>{notFoundMessage}</span>
            </div>
          ) : suggestions.length > 0 ? (
            <div className="divide-y divide-slate-800/80">
              <div className="bg-slate-900/60 px-4 py-2 text-[10px] font-mono uppercase tracking-wider text-slate-400 flex justify-between">
                <span>Verified Dataset Matches</span>
                <span>Review Count</span>
              </div>
              {suggestions.map((item) => (
                <button
                  key={item.product_id}
                  type="button"
                  onClick={() => handleSelect(item)}
                  className={`w-full flex items-center justify-between p-3.5 text-left text-xs transition hover:bg-purple-600/15 ${
                    selectedProductId === item.product_id ? 'bg-purple-600/20 border-l-2 border-purple-500' : ''
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-950/60 border border-indigo-500/30 text-indigo-400 shrink-0">
                      <Package className="h-4 w-4" />
                    </div>
                    <div>
                      <div className="font-semibold text-white">{item.product_title}</div>
                      <div className="text-[11px] text-slate-400 font-mono">
                        {item.category || 'General'} • ID: {item.product_id}
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-3">
                    <div className="text-right">
                      <div className="font-mono font-bold text-amber-400">{item.average_rating} ★</div>
                      <div className="text-[10px] text-slate-500">{item.review_count.toLocaleString()} reviews</div>
                    </div>
                    <ArrowRight className="h-3.5 w-3.5 text-slate-500" />
                  </div>
                </button>
              ))}
            </div>
          ) : null}
        </div>
      )}
    </div>
  );
};
