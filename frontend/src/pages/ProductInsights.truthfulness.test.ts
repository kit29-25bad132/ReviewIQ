import React from 'react';
import { describe, expect, it, vi } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';

vi.mock('../services/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../services/api')>();
  return {
    ...actual,
    // Effects never run during server rendering; mocks guarantee a loud
    // failure if an API call is ever moved into the render path.
    getProductAnalysis: vi.fn(() =>
      Promise.reject(new Error('network disabled in tests'))
    ),
    getOverview: vi.fn(() =>
      Promise.reject(new Error('network disabled in tests'))
    ),
    getProducts: vi.fn(() =>
      Promise.reject(new Error('network disabled in tests'))
    ),
  };
});

import { ProductInsights } from './ProductInsights';

// Renders the initial (pre-effect) markup only.
const renderInitial = (): string =>
  renderToStaticMarkup(React.createElement(ProductInsights, {}));

describe('ProductInsights truthfulness (Gate 1)', () => {
  const html = renderInitial();

  it('does not present seeded product metrics as actual data', () => {
    // Note: "Electric Toothbrush" may legitimately appear as a quick-search
    // chip in ProductSearch (a navigation seed that triggers a real API
    // search). The fabricated seed *metrics* must never be rendered.
    expect(html).not.toContain('3.64');
    expect(html).not.toContain('Loading Product...');
  });

  it('shows an explicit empty state until a product is loaded', () => {
    expect(html).toContain('No product selected');
  });

  it('uses provider-neutral wording', () => {
    expect(html).not.toContain('Gemini');
  });
});
