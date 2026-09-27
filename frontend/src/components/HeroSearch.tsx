import React, { useState } from 'react';
import { Search, Star, MessageSquare, ChevronRight, Loader2, AlertCircle, Sparkles } from 'lucide-react';
import { searchProducts } from '../services/api';
import { ProductSummary } from '../types/ecommerce';

interface HeroSearchProps {
  onSelectProduct: (product: ProductSummary) => void;
  initialQuery?: string;
}

export const HeroSearch: React.FC<HeroSearchProps> = ({
  onSelectProduct,
  initialQuery = '',
}) => {
  const [query, setQuery] = useState(initialQuery);
  const [isSearching, setIsSearching] = useState(false);
  const [results, setResults] = useState<ProductSummary[]>([]);
  const [hasSearched, setHasSearched] = useState(false);
  const [searchMessage, setSearchMessage] = useState<string | null>(null);
  const [searchError, setSearchError] = useState<string | null>(null);

  const handleSearch = async (searchTerm?: string) => {
    const q = (searchTerm !== undefined ? searchTerm : query).trim();
    if (!q) return;

    setIsSearching(true);
    setSearchError(null);
    setSearchMessage(null);
    setHasSearched(true);

    try {
      const response = await searchProducts(q, 24);
      if (response && response.products) {
        setResults(response.products);
        if (!response.found || response.products.length === 0) {
          setSearchMessage(
            response.message || 'No products found matching this name in the 4M review dataset.'
          );
        }
      } else {
        setResults([]);
        setSearchMessage('No matching products found.');
      }
    } catch (err) {
      setResults([]);
      setSearchError(
        err instanceof Error ? err.message : 'Unable to connect to the product search service.'
      );
    } finally {
      setIsSearching(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleSearch();
    }
  };

  const handleSampleClick = (sampleTerm: string) => {
    setQuery(sampleTerm);
    handleSearch(sampleTerm);
  };

  return (
    <div className="w-full">
      {/* Search Bar Container */}
      <div className="relative mx-auto max-w-3xl">
        <div className="flex flex-col sm:flex-row items-center gap-2 rounded-xl border border-[#292A2B] bg-[#151617] p-2 shadow-panel focus-within:border-[#D4AF5A]/60 focus-within:ring-1 focus-within:ring-[#D4AF5A]/30 transition">
          <div className="flex flex-1 items-center gap-3 px-3 py-1.5 w-full">
            <Search className="h-5 w-5 text-[#AAA79F] shrink-0" />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Search product by title, brand, or ASIN (e.g. Wireless Headphones, Kindle, Echo)..."
              className="w-full bg-transparent text-sm text-[#F5F2EA] placeholder:text-[#74736E] focus:outline-none"
            />
          </div>

          <button
            onClick={() => handleSearch()}
            disabled={isSearching || !query.trim()}
            className="gold-button flex w-full sm:w-auto items-center justify-center gap-2 px-6 py-3 text-xs font-semibold disabled:opacity-50 disabled:cursor-not-allowed shrink-0"
          >
            {isSearching ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Searching...
              </>
            ) : (
              <>
                <Sparkles className="h-4 w-4" />
                Analyze Product
              </>
            )}
          </button>
        </div>

        {/* Suggested Queries / Real Samples from Dataset */}
        <div className="mt-3 flex flex-wrap items-center gap-2 px-1 text-xs text-[#74736E]">
          <span className="font-medium">Quick search:</span>
          {['Headphones', 'Kindle', 'Echo Dot', 'Fire Tablet', 'Speaker', 'Keyboard', 'Camera'].map(
            (term) => (
              <button
                key={term}
                type="button"
                onClick={() => handleSampleClick(term)}
                className="rounded-md border border-[#292A2B] bg-[#121314] px-2.5 py-1 text-[11px] text-[#AAA79F] transition hover:border-[#D4AF5A]/40 hover:text-[#F0D58A]"
              >
                {term}
              </button>
            )
          )}
        </div>
      </div>

      {/* Search Error State */}
      {searchError && (
        <div className="mx-auto mt-6 max-w-2xl rounded-xl border border-rose-900/40 bg-rose-950/20 p-4 text-xs text-rose-300 flex items-start gap-3">
          <AlertCircle className="h-4 w-4 shrink-0 mt-0.5 text-rose-400" />
          <div className="flex-1">
            <p className="font-semibold text-rose-200">Search Error</p>
            <p className="mt-1 leading-relaxed">{searchError}</p>
          </div>
        </div>
      )}

      {/* No Results Message */}
      {hasSearched && !isSearching && !searchError && results.length === 0 && (
        <div className="premium-panel mx-auto mt-8 max-w-xl p-8 text-center border border-[#292A2B]">
          <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-xl border border-[#292A2B] bg-[#1A1815] text-[#D4AF5A]">
            <Search className="h-5 w-5" />
          </div>
          <h4 className="text-base font-medium text-[#F5F2EA]">No Matching Products Found</h4>
          <p className="mt-2 text-xs leading-relaxed text-[#AAA79F]">
            {searchMessage ||
              `No products matched "${query}". Please check your spelling or search by general keyword like "phone", "audio", or "camera".`}
          </p>
        </div>
      )}

      {/* Matching Products Grid */}
      {results.length > 0 && (
        <div className="mt-8">
          <div className="mb-4 flex items-center justify-between">
            <p className="text-xs uppercase tracking-[0.18em] text-[#AAA79F]">
              Found{' '}
              <span className="font-semibold text-[#F0D58A]">{results.length}</span>{' '}
              matching products in dataset
            </p>
            <span className="text-[11px] text-[#74736E]">Select a product to view intelligence</span>
          </div>

          <div className="grid gap-3.5 sm:grid-cols-2 lg:grid-cols-3">
            {results.map((product) => (
              <div
                key={product.product_id}
                onClick={() => onSelectProduct(product)}
                className="premium-panel premium-panel-hover group flex flex-col justify-between p-5 cursor-pointer border border-[#292A2B] transition-all hover:border-[#D4AF5A]/50 hover:bg-[#18191B]"
                role="button"
                tabIndex={0}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    onSelectProduct(product);
                  }
                }}
              >
                <div>
                  <div className="mb-3 flex items-center justify-between gap-2">
                    <span className="inline-block max-w-[180px] truncate rounded bg-[#1C1D1F] px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider text-[#AAA79F] border border-[#2A2B2D]">
                      {product.category || 'General Product'}
                    </span>
                    <span className="text-[10px] text-[#74736E] font-mono">
                      ID: {product.product_id}
                    </span>
                  </div>

                  <h4 className="line-clamp-2 text-sm font-semibold text-[#F5F2EA] group-hover:text-[#F0D58A] transition-colors leading-snug">
                    {product.product_title}
                  </h4>
                </div>

                <div className="mt-5 pt-3 border-t border-[#242526] flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="flex items-center gap-1 text-xs font-semibold text-[#F0D58A]">
                      <Star className="h-3.5 w-3.5 fill-[#D4AF5A] text-[#D4AF5A]" />
                      <span>{product.average_rating ? product.average_rating.toFixed(1) : 'N/A'}</span>
                    </div>

                    <div className="flex items-center gap-1 text-[11px] text-[#AAA79F]">
                      <MessageSquare className="h-3 w-3 text-[#74736E]" />
                      <span>{product.review_count.toLocaleString()} reviews</span>
                    </div>
                  </div>

                  <span className="flex items-center gap-1 text-xs font-medium text-[#D4AF5A] group-hover:translate-x-0.5 transition-transform">
                    Analyze
                    <ChevronRight className="h-3.5 w-3.5" />
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
