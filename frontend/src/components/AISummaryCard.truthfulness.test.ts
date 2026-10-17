import React from 'react';
import { describe, expect, it, vi } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';

vi.mock('../services/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../services/api')>();
  return {
    ...actual,
    // Effects never run during server rendering; the mock guarantees a loud
    // failure if a summary call is ever moved into the render path.
    generateAISummary: vi.fn(() =>
      Promise.reject(new Error('network disabled in tests'))
    ),
  };
});

import { handleApiError } from '../services/api';
import { IntelligenceSummary } from './IntelligenceSummary';
import type { ProductIntelligence } from '../types/intelligence';

// The AISummaryCard component this file originally covered was intentionally
// removed by Phase 5 and replaced by the intelligence stack: error messages
// now flow through handleApiError (services/api.ts) and the summary renders
// through IntelligenceSummary. The Gate 3/Gate 4 assertions below exercise
// those live replacements; the truthfulness intent of every original test is
// preserved.
const GENERIC = 'Unable to generate an AI summary right now. Please try again.';

const axiosLikeError = (overrides: {
  message?: string;
  response?: { status?: number; data?: unknown };
  request?: unknown;
}) =>
  Object.assign(new Error(overrides.message ?? 'Request failed with status code'), {
    isAxiosError: true,
    ...overrides,
  });

// handleApiError reports failures by throwing; capture the message a UI would
// render instead of the raw error object.
const caughtMessage = (fn: () => unknown): string => {
  try {
    fn();
    return '<no error thrown>';
  } catch (err) {
    return err instanceof Error ? err.message : String(err);
  }
};

describe('summary error messages (Gate 3)', () => {
  it('uses the safe server-provided detail on HTTP 500', () => {
    const message = caughtMessage(() =>
      handleApiError(
        axiosLikeError({
          response: {
            status: 500,
            data: {
              detail:
                'Connection to AI service timed out or unavailable. Please verify your network connection.',
            },
          },
        }),
        GENERIC
      )
    );
    expect(message).toBe(
      'Connection to AI service timed out or unavailable. Please verify your network connection.'
    );
  });

  it('uses the safe server-provided detail on HTTP 400', () => {
    const message = caughtMessage(() =>
      handleApiError(
        axiosLikeError({
          response: {
            status: 400,
            data: { detail: 'AI summary failed validation. Please try again.' },
          },
        }),
        GENERIC
      )
    );
    expect(message).toBe('AI summary failed validation. Please try again.');
  });

  it('falls back to a concise safe message on network failure (no response)', () => {
    const message = caughtMessage(() =>
      handleApiError(
        axiosLikeError({ request: {}, message: 'Network Error' }),
        GENERIC
      )
    );
    expect(message).toContain('Backend Offline: Cannot connect');
    expect(message).not.toContain('Network Error');
    expect(message).not.toContain('[object Object]');
  });

  it('ignores missing, empty, or non-string detail values', () => {
    const status500 = 'AI analysis service encountered an error. Please try again.';
    expect(
      caughtMessage(() =>
        handleApiError(axiosLikeError({ response: { status: 500, data: {} } }), GENERIC)
      )
    ).toBe(status500);
    expect(
      caughtMessage(() =>
        handleApiError(
          axiosLikeError({ response: { status: 500, data: { detail: '' } } }),
          GENERIC
        )
      )
    ).toBe(status500);
    expect(
      caughtMessage(() =>
        handleApiError(
          axiosLikeError({ response: { status: 500, data: { detail: '   ' } } }),
          GENERIC
        )
      )
    ).toBe(status500);
    expect(
      caughtMessage(() =>
        handleApiError(
          axiosLikeError({ response: { status: 500, data: { detail: { obj: true } } } }),
          GENERIC
        )
      )
    ).toBe(status500);
    expect(caughtMessage(() => handleApiError({ response: {} }, GENERIC))).toBe(GENERIC);
    expect(caughtMessage(() => handleApiError({ response: { data: {} } }, GENERIC))).toBe(
      GENERIC
    );
    expect(caughtMessage(() => handleApiError(undefined, GENERIC))).toBe(GENERIC);
    expect(caughtMessage(() => handleApiError('plain string failure', GENERIC))).toBe(GENERIC);
  });

  it('never renders raw exception objects or sensitive canary text', () => {
    const canary = 'sk-live-canary-123 internals=/var/log/x';
    const message = caughtMessage(() =>
      handleApiError(
        axiosLikeError({
          message: canary,
          response: {
            status: 500,
            data: {
              detail: 'AI analysis is unavailable. Please check the server configuration.',
            },
          },
        }),
        GENERIC
      )
    );
    expect(message).toBe(
      'AI analysis is unavailable. Please check the server configuration.'
    );
    expect(message).not.toContain(canary);
    expect(message).not.toContain('sk-live');
    expect(message).not.toContain('Error:');
    expect(message).not.toContain('[object Object]');
  });
});

const makeIntelligence = (
  overrides: Partial<ProductIntelligence> = {}
): ProductIntelligence => ({
  product_id: '9640962',
  product_name: 'Test Product',
  statistics: {
    total_reviews: 42,
    average_rating: 4.2,
    rating_distribution: { '5': 20, '4': 15, '3': 4, '2': 2, '1': 1 },
    sentiment_distribution: { positive: 30, neutral: 8, negative: 4 },
    verified_purchase_pct: 80,
    date_range: { earliest: '2025-01-01', latest: '2025-12-31' },
  },
  aspects: [],
  pros: [],
  cons: [],
  summary: '',
  best_for: '',
  data_source: 'supabase',
  review_count_used: 42,
  generated_at: '2026-01-01T00:00:00Z',
  low_review_count: false,
  ai_unavailable: false,
  ...overrides,
});

const renderSummary = (intelligence: ProductIntelligence): string =>
  renderToStaticMarkup(React.createElement(IntelligenceSummary, { intelligence }));

const unavailableHtml = (): string =>
  renderSummary(makeIntelligence({ ai_unavailable: true, summary: '' }));

const generatedHtml = (): string =>
  renderSummary(
    makeIntelligence({
      summary: 'Customers like the clean design and long battery.',
      best_for: 'Everyday buyers',
    })
  );

describe('summary content vs. empty state (Gate 3)', () => {
  it('renders a generated summary verbatim', () => {
    const html = generatedHtml();
    expect(html).toContain('Customers like the clean design and long battery.');
    expect(html).not.toContain('No customer reviews are available');
  });

  it('never presents the "no reviews available" empty state as generated output', () => {
    // The explicit backend empty state is reported upstream as a structured
    // error; neither render path may surface it as AI-generated content.
    expect(unavailableHtml()).not.toContain('No customer reviews are available');
    expect(generatedHtml()).not.toContain('No customer reviews are available');
  });
});

describe('IntelligenceSummary rendering (Gate 3/Gate 4)', () => {
  it('shows the explicit unavailable state instead of a fabricated or stale summary', () => {
    const html = unavailableHtml();
    expect(html).toContain('AI analysis unavailable');
    expect(html).toContain(
      'the AI summary could not be generated. No AI content is shown rather than showing unverified content.'
    );
    expect(html).not.toContain('No customer reviews are available');
  });

  it('does not claim AI generation before any summary exists (Gate 4)', () => {
    const html = unavailableHtml();
    expect(html).not.toContain('AI-generated');
    expect(html).not.toContain('constrained strictly to dataset reviews');
  });

  it('keeps provider wording neutral', () => {
    expect(unavailableHtml()).not.toContain('Gemini');
    expect(generatedHtml()).not.toContain('Gemini');
  });

  it('reports the grounding count exactly as supplied by the payload (no derived pool arithmetic)', () => {
    const html = generatedHtml();
    expect(html).toContain('Grounded in 42 reviews');
    expect(html).not.toContain('available reviews');
    expect(html).not.toContain('Analyzed sample');
  });

  it('surfaces the backend low-review-count flag as reported', () => {
    const html = renderSummary(makeIntelligence({ low_review_count: true }));
    expect(html).toContain('Low review count');
  });
});
