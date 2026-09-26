import React, { useState, useEffect, useRef } from 'react';
import { Search, XCircle, Package, ArrowRight, AlertCircle, Sparkles } from 'lucide-react';
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
          <Search className="absolute left-4 h-5 w-5 text-[#D4AF5A] pointer-events-none" />
          <input
            type="text"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setIsOpen(true);
            }}
            onFocus={() => setIsOpen(true)}
            placeholder="Search product name... (e.g. Electric Toothbrush, Noise-Canceling Headphones)"
            className="w-full rounded-xl border border-[#292A2B] bg-[#151617] py-4 pl-12 pr-28 text-sm sm:text-base text-[#F5F2EA] placeholder-[#74736E] shadow-2xl focus:border-[#D4AF5A]/60 focus:outline-none focus:ring-2 focus:ring-[#D4AF5A]/20 transition duration-200"
          />

          <div className="absolute right-3 flex items-center gap-2">
            {query && (
              <button
                type="button"
                onClick={handleClear}
                className="p-1 text-[#74736E] hover:text-[#F5F2EA] transition"
                title="Clear search"
              >
                <XCircle className="h-4 w-4" />
              </button>
            )}

            <button
              type="submit"
              disabled={loading || suggestions.length === 0}
              className="gold-button inline-flex items-center gap-1.5 px-4 py-2 text-xs font-semibold disabled:opacity-40"
            >
              <Sparkles className="h-3.5 w-3.5" />
              <span>{loading ? 'Searching...' : 'Analyze'}</span>
            </button>
          </div>
        </div>
      </form>

      {/* Live Dropdown Suggestions */}
      {isOpen && (suggestions.length > 0 || loading || notFoundMessage) && (
        <div className="absolute top-full left-0 right-0 z-50 mt-2 max-h-96 overflow-y-auto rounded-xl border border-[#292A2B] bg-[#151617] shadow-[0_20px_60px_rgba(0,0,0,0.8)] backdrop-blur-xl">
          {loading && suggestions.length === 0 && (
            <div className="flex items-center justify-center p-6 text-sm text-[#AAA79F]">
              <div className="mr-3 h-4 w-4 animate-spin rounded-full border-2 border-[#D4AF5A] border-t-transparent" />
              Searching review dataset...
            </div>
          )}

          {notFoundMessage && !loading && (
            <div className="flex items-center gap-3 p-4 text-sm text-[#AAA79F]">
              <AlertCircle className="h-5 w-5 flex-shrink-0 text-amber-500" />
              <span>{notFoundMessage}</span>
            </div>
          )}

          {suggestions.map((item) => {
            const isSelected = selectedProductId === item.product_id;
            return (
              <button
                key={item.product_id}
                onClick={() => handleSelect(item)}
                className={`group flex w-full items-center justify-between border-b border-[#292A2B]/60 p-4 text-left transition hover:bg-[#1C1D1F] last:border-0 ${
                  isSelected ? 'bg-[#1C1D1F] border-l-4 border-l-[#D4AF5A]' : ''
                }`}
              >
                <div className="flex items-start gap-3">
                  <div className="mt-0.5 rounded-lg border border-[#292A2B] bg-[#111213] p-2 text-[#D4AF5A]">
                    <Package className="h-4 w-4" />
                  </div>
                  <div>
                    <h4 className="text-sm font-medium text-[#F5F2EA] group-hover:text-[#F0D58A] transition">
                      {item.product_title}
                    </h4>
                    <p className="mt-0.5 text-xs text-[#74736E]">
                      {item.category || 'Product'} · {item.review_count.toLocaleString()} real customer reviews
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-3">
                  <div className="text-right">
                    <span className="text-sm font-semibold text-[#D4AF5A]">
                      ★ {item.average_rating.toFixed(1)}
                    </span>
                    <span className="text-[10px] text-[#74736E] block">/ 5.0</span>
                  </div>
                  <ArrowRight className="h-4 w-4 text-[#74736E] transition group-hover:translate-x-1 group-hover:text-[#F0D58A]" />
                </div>
              </button>
            );
          })}
        </div>
      )}

      {/* Quick Test Suggested Products */}
      <div className="flex flex-wrap items-center gap-2 pt-1">
        <span className="text-xs text-[#74736E] font-medium flex items-center gap-1.5">
          <Sparkles className="h-3 w-3 text-[#D4AF5A]" />
          Quick Test:
        </span>
        {SAMPLE_PRODUCTS.map((prod) => (
          <button
            key={prod}
            type="button"
            onClick={() => handleQuickChip(prod)}
            className="rounded-lg border border-[#292A2B] bg-[#151617] px-3 py-1.5 text-xs text-[#AAA79F] transition hover:border-[#D4AF5A]/40 hover:bg-[#1C1D1F] hover:text-[#F5F2EA]"
          >
            {prod}
          </button>
        ))}
      </div>
    </div>
  );
};
