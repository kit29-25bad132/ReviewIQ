import React, { useState } from 'react';
import { Dashboard } from './pages/Dashboard';
import { AnalyzeReview } from './pages/AnalyzeReview';
import { ReviewHistory } from './pages/ReviewHistory';
import { ProductInsights } from './pages/ProductInsights';

export type Page =
  | 'dashboard'
  | 'analyze'
  | 'history'
  | 'insights'
  | 'compare'
  | 'categories'
  | 'trends'
  | 'settings';

export const App: React.FC = () => {
  const [page, setPage] = useState<Page>('dashboard');

  const renderPage = () => {
    switch (page) {
      case 'dashboard':
        return <Dashboard onNavigate={setPage} />;

      case 'analyze':
        return (
          <AnalyzeReview
            onBack={() => setPage('dashboard')}
          />
        );

      case 'history':
        return (
          <ReviewHistory
            onBack={() => setPage('dashboard')}
          />
        );

      case 'insights':
        return (
          <ProductInsights
            onBack={() => setPage('dashboard')}
          />
        );

      case 'compare':
        return (
          <SimplePage
            title="Compare Products"
            onNavigate={setPage}
          />
        );

      case 'categories':
        return (
          <SimplePage
            title="Categories"
            onNavigate={setPage}
          />
        );

      case 'trends':
        return (
          <SimplePage
            title="Trends"
            onNavigate={setPage}
          />
        );

      case 'settings':
        return (
          <SimplePage
            title="Settings"
            onNavigate={setPage}
          />
        );

      default:
        return <Dashboard onNavigate={setPage} />;
    }
  };

  return (
    <div className="min-h-screen">
      {renderPage()}
    </div>
  );
};

interface SimplePageProps {
  title: string;
  onNavigate: (page: Page) => void;
}

const SimplePage: React.FC<SimplePageProps> = ({
  title,
  onNavigate,
}) => {
  return (
    <div className="min-h-screen bg-[#0E0F10] text-[#F5F2EA] flex items-center justify-center px-6">
      <div className="text-center">

        <div className="mx-auto mb-6 flex h-10 w-10 items-center justify-center rounded-lg border border-[#D4AF5A]/30 bg-[#191714]">
          <span className="text-sm text-[#D4AF5A]">✦</span>
        </div>

        <p className="text-[#D4AF5A] text-[10px] uppercase tracking-[0.22em]">
          ReviewIQ
        </p>

        <h1 className="mt-3 text-3xl font-medium tracking-tight">
          {title}
        </h1>

        <p className="mt-3 text-sm text-[#74736E]">
          This section will be built next.
        </p>

        <button
          onClick={() => onNavigate('dashboard')}
          className="gold-button mt-7 px-5 py-2.5 text-sm"
        >
          Back to Dashboard
        </button>

      </div>
    </div>
  );
};

export default App;