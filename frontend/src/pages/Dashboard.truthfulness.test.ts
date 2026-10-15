import React from 'react';
import { describe, expect, it, vi } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';

// Storage module touches browser localStorage; stub it for the node test env.
vi.mock('../services/historyStorage', () => ({
  fetchAllReviews: vi.fn().mockResolvedValue({ reviews: [], source: 'local' }),
  saveReviewAnalysis: vi.fn(),
  deleteReviewById: vi.fn(),
  clearAllReviews: vi.fn(),
  getLocalReviews: vi.fn(() => []),
}));

vi.mock('../services/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../services/api')>();
  return {
    ...actual,
    // Effects never run during server rendering, so no calls are expected;
    // the mocks exist only to guarantee a failure if that ever changes.
    getProductAnalysis: vi.fn(() =>
      Promise.reject(new Error('network disabled in tests'))
    ),
    checkBackendHealth: vi.fn(() =>
      Promise.resolve({ status: 'ok', ai_configured: false, ai_provider: '' })
    ),
  };
});

import { Dashboard } from './Dashboard';

// Renders the initial (pre-effect) markup only; useEffect callbacks do not run
// during server rendering, which matches the state a user sees while the
// featured analysis request is still in flight.
const renderInitial = (): string =>
  renderToStaticMarkup(React.createElement(Dashboard));

describe('Dashboard hero preview truthfulness (Gate 1)', () => {
  const html = renderInitial();

  it('does not render fabricated fallback rating or review counts', () => {
    expect(html).not.toContain('4.5');
    expect(html).not.toContain('156');
  });

  it('does not render the fabricated aspect preview table or its ratings', () => {
    expect(html).not.toContain('Quality & Durability');
    expect(html).not.toContain('Value for Money');
    expect(html).not.toContain('Battery Life');
    expect(html).not.toContain('Ease of Use');
  });

  it('does not render the misleading "AI analyzed" badge', () => {
    expect(html).not.toContain('AI analyzed');
  });

  it('shows a truthful loading state instead of placeholder metrics', () => {
    expect(html).toContain('Featured dataset product');
    expect(html).toContain('Loading featured product analysis');
  });

  it('uses provider-neutral wording while provider identity is unavailable', () => {
    expect(html).not.toContain('Gemini');
  });
});
