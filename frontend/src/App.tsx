import React, { useState } from 'react';
import { Navbar, NavTab } from './components/Navbar';
import { HomePage } from './pages/HomePage';
import { SearchPage } from './pages/SearchPage';
import { DashboardPage } from './pages/DashboardPage';
import { HistoryPage } from './pages/HistoryPage';
import { SingleReviewAnalyzer } from './components/SingleReviewAnalyzer';
import { ProductSummary } from './types/ecommerce';

export const App: React.FC = () => {
  const [currentTab, setCurrentTab] = useState<NavTab>('home');
  const [activeProduct, setActiveProduct] = useState<ProductSummary | null>(null);

  const handleSelectProduct = (product: ProductSummary) => {
    setActiveProduct(product);
    setCurrentTab('dashboard');
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const handleBackToSearch = () => {
    setCurrentTab('search');
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const renderContent = () => {
    switch (currentTab) {
      case 'home':
        return (
          <HomePage
            onSelectProduct={handleSelectProduct}
            onNavigateToAnalyzer={() => setCurrentTab('analyzer')}
            onNavigateToSearch={() => setCurrentTab('search')}
          />
        );

      case 'search':
        return <SearchPage onSelectProduct={handleSelectProduct} />;

      case 'dashboard':
        if (!activeProduct) {
          return <SearchPage onSelectProduct={handleSelectProduct} />;
        }
        return (
          <DashboardPage
            productId={activeProduct.product_id}
            initialProduct={activeProduct}
            onBackToSearch={handleBackToSearch}
          />
        );

      case 'analyzer':
        return <SingleReviewAnalyzer />;

      case 'history':
        return <HistoryPage onSelectProduct={handleSelectProduct} />;

      default:
        return (
          <HomePage
            onSelectProduct={handleSelectProduct}
            onNavigateToAnalyzer={() => setCurrentTab('analyzer')}
            onNavigateToSearch={() => setCurrentTab('search')}
          />
        );
    }
  };

  return (
    <div className="min-h-screen bg-[#0E0F10] text-[#F5F2EA] flex flex-col font-sans selection:bg-[#D4AF5A]/30 selection:text-[#FFF8E6]">
      {/* Top Navigation */}
      <Navbar
        currentTab={currentTab}
        onNavigate={(tab) => {
          setCurrentTab(tab);
          window.scrollTo({ top: 0, behavior: 'smooth' });
        }}
        hasActiveProduct={!!activeProduct}
      />

      {/* Main View Area */}
      <main className="flex-1">{renderContent()}</main>

      {/* Enterprise Footer */}
      <footer className="border-t border-[#242526] bg-[#0A0B0C] py-8 text-xs text-[#74736E]">
        <div className="mx-auto flex max-w-7xl flex-col sm:flex-row items-center justify-between gap-4 px-4 sm:px-6 lg:px-8">
          <div className="flex items-center gap-2">
            <span className="font-semibold tracking-[0.16em] text-[#AAA79F]">
              REVIEW<span className="text-[#D4AF5A]">IQ</span>
            </span>
            <span>—</span>
            <span>AI-Powered Product Intelligence Platform</span>
          </div>

          <div className="flex items-center gap-4 text-[11px]">
            <span>Grounded on 4M Review Dataset</span>
            <span>•</span>
            <span>Zero Synthetic Hallucinations</span>
            <span>•</span>
            <span>FastAPI & LangGraph AI</span>
          </div>
        </div>
      </footer>
    </div>
  );
};

export default App;