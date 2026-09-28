import React, { useState, useEffect, useRef } from 'react';
import { Search, XCircle, Package, ArrowRight, AlertCircle, Sparkles } from 'lucide-react';
import { ProductSummary } from '../types/ecommerce';
import { searchProducts } from '../services/api';

interface ProductSearchProps {
  onSelectProduct: (product: ProductSummary) => void;
  onTriggerAnalyze?: (product: ProductSummary) => void;
  selectedProductId?: string;
  isAnalyzing?: boolean;
  activeProductName?: string;
  placeholder?: string;
  compact?: boolean;
}

export const ProductSearch: React.FC<ProductSearchProps> = ({
  onSelectProduct,
  onTriggerAnalyze,
  selectedProductId,
  isAnalyzing = false,
  activeProductName,
  placeholder,
  compact = false,
}) => {
  const [query, setQuery] = useState<string>('');
  const [suggestions, setSuggestions] = useState<ProductSummary[]>([]);
  const [popularProducts, setPopularProducts] = useState<ProductSummary[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [isOpen, setIsOpen] = useState<boolean>(false);
  const [notFoundMessage, setNotFoundMessage] = useState<string | null>(null);
  const [busyWarning, setBusyWarning] = useState<string | null>(null);
  const wrapperRef = useRef<HTMLDivElement>(null);

  // Load real dataset products for quick test chips
  useEffect(() => {
    searchProducts('', 6)
      .then((res) => {
        if (res.found && res.products.length > 0) {
          setPopularProducts(res.products);
        }
      })
      .catch(() => {});
  }, []);

  const showBusyNotification = () => {
    const prodName = activeProductName ? `"${activeProductName}"` : 'current product';
    setBusyWarning(`⚠️ Analysis is currently in progress for ${prodName}. Please wait for it to finish before selecting another product.`);
    setTimeout(() => {
      setBusyWarning(null);
    }, 4500);
  };

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

  // Normal pick / selection without auto-analyzing
  const handlePickProduct = (product: ProductSummary) => {
    if (isAnalyzing) {
      showBusyNotification();
      setIsOpen(false);
      return;
    }
    setBusyWarning(null);
    setQuery(product.product_title);
    setIsOpen(false);
    onSelectProduct(product);
  };

  const handleClear = () => {
    if (isAnalyzing) {
      showBusyNotification();
      return;
    }
    setQuery('');
    setSuggestions([]);
    setNotFoundMessage(null);
    setIsOpen(false);
  };

  // Explicit Analyze button trigger
  const handleAnalyzeSubmit = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (isAnalyzing) {
      showBusyNotification();
      return;
    }
    if (!query.trim()) return;

    const executeTrigger = (prod: ProductSummary) => {
      if (onTriggerAnalyze) {
        onTriggerAnalyze(prod);
      } else {
        onSelectProduct(prod);
      }
    };

    if (suggestions.length > 0) {
      const topMatch = suggestions[0];
      setQuery(topMatch.product_title);
      setIsOpen(false);
      executeTrigger(topMatch);
      return;
    }

    setLoading(true);
    setNotFoundMessage(null);
    try {
      const res = await searchProducts(query.trim(), 5);
      if (res.found && res.products.length > 0) {
        const topMatch = res.products[0];
        setQuery(topMatch.product_title);
        setIsOpen(false);
        executeTrigger(topMatch);
      } else {
        setNotFoundMessage(res.message || 'Product not found in the available review dataset.');
        setIsOpen(true);
      }
    } catch {
      setNotFoundMessage('Failed to query review dataset.');
      setIsOpen(true);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div ref={wrapperRef} className="relative w-full space-y-3">
      {/* Busy Warning Banner */}
      {busyWarning && (
        <div className="flex items-center gap-2.5 rounded-xl border border-amber-300 bg-amber-50 px-4 py-3 text-xs font-medium text-amber-800 shadow-sm transition animate-bounce">
          <AlertCircle className="h-4 w-4 text-amber-600 shrink-0" />
          <span>{busyWarning}</span>
        </div>
      )}

      {/* Search Input Box */}
      <form onSubmit={handleAnalyzeSubmit} className="relative">
        <div className="relative flex items-center">
          <Search className="absolute left-4 h-5 w-5 text-indigo-500 pointer-events-none" />
          <input
            type="text"
            value={query}
            disabled={isAnalyzing}
            onChange={(e) => {
              setQuery(e.target.value);
              setIsOpen(true);
            }}
            onFocus={() => {
              if (!isAnalyzing) setIsOpen(true);
            }}
            placeholder={
              isAnalyzing
                ? `Analyzing ${activeProductName || 'product'}... Please wait.`
                : placeholder || "Search for a product (e.g. Electric Toothbrush, Headphones, Blender...)"
            }
            className={`w-full rounded-2xl border border-slate-200 bg-white py-3.5 pl-12 pr-28 text-sm text-slate-800 placeholder-slate-400 shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-4 focus:ring-indigo-100/60 transition-all duration-200 ${
              isAnalyzing ? 'opacity-60 cursor-not-allowed bg-slate-50' : ''
            }`}
          />

          <div className="absolute right-2.5 flex items-center gap-2">
            {query && !isAnalyzing && (
              <button
                type="button"
                onClick={handleClear}
                className="p-1 text-slate-400 hover:text-slate-600 transition"
                title="Clear search"
              >
                <XCircle className="h-4 w-4" />
              </button>
            )}

            <button
              type="submit"
              disabled={isAnalyzing || loading || !query.trim()}
              className="primary-button inline-flex items-center gap-1.5 px-4 py-2 text-xs font-semibold"
            >
              <Sparkles className={`h-3.5 w-3.5 ${isAnalyzing ? 'animate-spin' : ''}`} />
              <span>{isAnalyzing ? 'Analyzing...' : loading ? 'Searching...' : 'Analyze'}</span>
            </button>
          </div>
        </div>
      </form>

      {/* Live Dropdown Suggestions */}
      {isOpen && (suggestions.length > 0 || loading || notFoundMessage) && (
        <div className="absolute top-full left-0 right-0 z-50 mt-2 max-h-96 overflow-y-auto rounded-2xl border border-slate-200 bg-white shadow-xl">
          {loading && suggestions.length === 0 && (
            <div className="flex items-center justify-center p-6 text-sm text-slate-500">
              <div className="mr-3 h-4 w-4 animate-spin rounded-full border-2 border-indigo-600 border-t-transparent" />
              Searching review dataset...
            </div>
          )}

          {notFoundMessage && !loading && (
            <div className="flex items-center gap-3 p-4 text-sm text-slate-600">
              <AlertCircle className="h-5 w-5 flex-shrink-0 text-amber-500" />
              <span>{notFoundMessage}</span>
            </div>
          )}

          {suggestions.map((item) => {
            const isSelected = selectedProductId === item.product_id;
            return (
              <button
                key={item.product_id}
                type="button"
                onClick={() => handlePickProduct(item)}
                className={`group flex w-full items-center justify-between border-b border-slate-100 p-4 text-left transition hover:bg-indigo-50/50 last:border-0 ${
                  isSelected ? 'bg-indigo-50/70 border-l-4 border-l-indigo-600' : ''
                }`}
              >
                <div className="flex items-start gap-3">
                  <div className="mt-0.5 rounded-xl border border-slate-200 bg-slate-50 p-2 text-indigo-600 group-hover:bg-indigo-600 group-hover:text-white transition">
                    <Package className="h-4 w-4" />
                  </div>
                  <div>
                    <h4 className="text-sm font-semibold text-slate-800 group-hover:text-indigo-600 transition">
                      {item.product_title}
                    </h4>
                    <p className="mt-0.5 text-xs text-slate-500">
                      {item.category || 'Product'} · {item.review_count.toLocaleString()} real customer reviews
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-3">
                  <div className="text-right">
                    <span className="text-sm font-bold text-amber-500">
                      ★ {item.average_rating.toFixed(1)}
                    </span>
                    <span className="text-[10px] text-slate-400 block">/ 5.0</span>
                  </div>
                  <ArrowRight className="h-4 w-4 text-slate-400 transition group-hover:translate-x-1 group-hover:text-indigo-600" />
                </div>
              </button>
            );
          })}
        </div>
      )}

      {/* Quick Test Suggested Products */}
      {!compact && popularProducts.length > 0 && (
        <div className="flex flex-wrap items-center gap-2 pt-1">
          <span className="text-xs text-slate-400 font-medium flex items-center gap-1.5">
            <Sparkles className="h-3.5 w-3.5 text-indigo-500" />
            Quick Test:
          </span>
          {popularProducts.map((prod) => (
            <button
              key={prod.product_id}
              type="button"
              onClick={() => handlePickProduct(prod)}
              className={`rounded-xl border border-slate-200/90 bg-white px-3 py-1.5 text-xs font-medium text-slate-600 shadow-xs transition ${
                isAnalyzing
                  ? 'opacity-60 cursor-not-allowed'
                  : 'hover:border-indigo-300 hover:bg-indigo-50/70 hover:text-indigo-600 active:scale-[0.98]'
              }`}
            >
              {prod.product_title}
            </button>
          ))}
        </div>
      )}
    </div>
  );
};
