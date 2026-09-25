import React, { useState } from 'react';
import { Dashboard } from './pages/Dashboard';
import { ProductInsights } from './pages/ProductInsights';

export type Page =
  | 'dashboard'
  | 'analyze'
  | 'history'
  | 'insights';

const App: React.FC = () => {
  const [page, setPage] = useState<Page>('dashboard');

  return (
    <div className="min-h-screen">
      {page === 'dashboard' && (
        <Dashboard onNavigate={setPage} />
      )}

      {page === 'insights' && (
        <ProductInsights
          onBack={() => setPage('dashboard')}
        />
      )}

      {(page === 'analyze' || page === 'history') && (
        <div className="flex min-h-screen items-center justify-center bg-[var(--bg-main)] px-6 text-[var(--text-primary)]">
          <div className="premium-panel max-w-md p-8 text-center">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] gold-text">
              ReviewIQ
            </p>

            <h2 className="mt-3 text-2xl font-semibold">
              Coming Soon
            </h2>

            <p className="mt-3 text-sm leading-6 text-[var(--text-secondary)]">
              This section will be connected to the product
              review analysis system later.
            </p>

            <button
              onClick={() => setPage('dashboard')}
              className="gold-button mt-6 px-5 py-2.5 text-sm"
            >
              Back to Home
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default App;