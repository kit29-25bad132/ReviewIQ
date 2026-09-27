import React from 'react';
import { Search } from 'lucide-react';
import { HeroSearch } from '../components/HeroSearch';
import { ProductSummary } from '../types/ecommerce';

interface SearchPageProps {
  onSelectProduct: (product: ProductSummary) => void;
}

export const SearchPage: React.FC<SearchPageProps> = ({ onSelectProduct }) => {
  return (
    <div className="mx-auto max-w-7xl px-4 py-10 sm:px-6 lg:px-8 space-y-8">
      {/* Title & Guidance */}
      <div className="border-b border-[#292A2B] pb-6">
        <div className="flex items-center gap-2 mb-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-lg border border-[#D4AF5A]/40 bg-[#1E1B15] text-[#D4AF5A]">
            <Search className="h-4 w-4" />
          </div>
          <span className="text-xs font-semibold uppercase tracking-[0.2em] text-[#D4AF5A]">
            Dataset Explorer
          </span>
        </div>

        <h1 className="text-2xl sm:text-3xl font-semibold tracking-tight text-[#F5F2EA]">
          Search Products in ReviewIQ Dataset
        </h1>
        <p className="mt-2 text-sm text-[#AAA79F] max-w-2xl leading-relaxed">
          Search across 4 million Amazon e-commerce customer reviews. Select any product to launch
          deep aspect mining, sentiment scoring, and evidence verification.
        </p>
      </div>

      {/* Embedded Search Component */}
      <div className="pt-2">
        <HeroSearch onSelectProduct={onSelectProduct} />
      </div>
    </div>
  );
};
