import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { ReviewAnalysis } from '../types/review';

const mocks = vi.hoisted(() => ({
  post: vi.fn(),
  get: vi.fn(),
}));

vi.mock('axios', () => {
  const isAxiosError = (error: unknown): boolean =>
    typeof error === 'object' &&
    error !== null &&
    (error as { isAxiosError?: boolean }).isAxiosError === true;

  const axiosDefault = {
    create: () => ({
      post: mocks.post,
      get: mocks.get,
      // unused handlers kept so accidental calls fail loudly in tests
      put: vi.fn(),
      delete: vi.fn(),
    }),
    isAxiosError,
  };

  return {
    default: axiosDefault,
    isAxiosError,
    AxiosError: class AxiosError extends Error {
      response?: unknown;
      code?: string;
      request?: unknown;
    },
  };
});

import { analyzeReview } from './api';

const fullAnalysis: ReviewAnalysis = {
  sentiment: 'mixed',
  rating: 4,
  rating_source: 'explicit',
  summary: 'Great camera, weak battery.',
  aspects: [
    { aspect: 'camera', sentiment: 'positive', evidence: 'camera is excellent' },
    { aspect: 'battery', sentiment: 'negative', evidence: 'battery life is poor' },
  ],
  pros: [{ point: 'Excellent camera', evidence: 'camera is excellent' }],
  cons: [{ point: 'Poor battery life', evidence: 'battery life is poor' }],
};

const makeAxiosError = (
  overrides: {
    message?: string;
    response?: { status: number; data?: unknown };
    code?: string;
    request?: unknown;
  } = {}
) => {
  const error = Object.assign(new Error(overrides.message || 'Request failed with status code'), {
    isAxiosError: true,
    ...overrides,
  });
  return error;
};

beforeEach(() => {
  mocks.post.mockReset();
  mocks.get.mockReset();
});

describe('analyzeReview', () => {
  it('A. unwraps the backend success envelope and preserves all analysis fields', async () => {
    mocks.post.mockResolvedValue({
      data: {
        success: true,
        data: fullAnalysis,
        error: null,
      },
    });

    const result = await analyzeReview('The camera is excellent but battery life is poor. 4 stars.');

    expect(result).toEqual(fullAnalysis);
    expect(result.sentiment).toBe('mixed');
    expect(result.rating).toBe(4);
    expect(result.rating_source).toBe('explicit');
    expect(result.summary).toBe(fullAnalysis.summary);
    expect(result.aspects).toHaveLength(2);
    expect(result.pros[0]).toEqual({
      point: 'Excellent camera',
      evidence: 'camera is excellent',
    });
    expect(result.cons[0]).toEqual({
      point: 'Poor battery life',
      evidence: 'battery life is poor',
    });
    expect(mocks.post).toHaveBeenCalledWith(
      '/api/analyze-review',
      { review: 'The camera is excellent but battery life is poor. 4 stars.' },
      expect.objectContaining({ timeout: 45000 })
    );
  });

  it('B. surfaces safe backend detail on HTTP error response', async () => {
    mocks.post.mockRejectedValue(
      makeAxiosError({
        response: {
          status: 400,
          data: { detail: 'Review analysis failed validation. Please try again.' },
        },
      })
    );

    await expect(analyzeReview('bad')).rejects.toThrow(
      'Review analysis failed validation. Please try again.'
    );
  });

  it('B2. uses status-based fallback when no detail is present (500)', async () => {
    mocks.post.mockRejectedValue(
      makeAxiosError({
        response: {
          status: 500,
          data: {},
        },
      })
    );

    await expect(analyzeReview('ok')).rejects.toThrow(
      'AI analysis service encountered an error. Please try again.'
    );
  });

  it('B3. timeout falls back to a local analysis instead of surfacing a timeout error', async () => {
    mocks.post.mockRejectedValue(
      makeAxiosError({
        code: 'ECONNABORTED',
      })
    );

    const result = await analyzeReview('slow');

    expect(result.rating).toBeGreaterThan(0);
    expect(result.rating).toBeLessThanOrEqual(5);
    expect(result.summary).toBeTruthy();
    expect(result.sentiment).toMatch(/positive|negative|mixed|neutral/);
  });

  it('B4. network failure without response falls back to a local analysis', async () => {
    mocks.post.mockRejectedValue(
      makeAxiosError({
        request: {},
      })
    );

    const result = await analyzeReview('x');

    expect(result.summary).toBeTruthy();
    expect(result.rating).toBeGreaterThan(0);
  });

  it('C. rejects when envelope reports success=false with error message', async () => {
    mocks.post.mockResolvedValue({
      data: {
        success: false,
        data: null,
        error: 'AI analysis failed. Please try again.',
      },
    });

    await expect(analyzeReview('anything')).rejects.toThrow(
      'AI analysis failed. Please try again.'
    );
  });

  it('C2. rejects when success envelope is missing analysis payload', async () => {
    mocks.post.mockResolvedValue({
      data: {
        success: true,
        data: null,
        error: null,
      },
    });

    await expect(analyzeReview('anything')).rejects.toThrow('Failed to analyze review');
  });

  it('C3. non-axios unexpected error surfaces a safe generic message', async () => {
    mocks.post.mockRejectedValue('plain-string-failure');

    await expect(analyzeReview('x')).rejects.toThrow(
      'An unknown error occurred while analyzing the review.'
    );
  });
});

describe('getProductAnalysis and searchProducts with configurable timeouts', () => {
  it('D1. getProductAnalysis uses 45-60s AI timeout and passes AbortSignal', async () => {
    const { getProductAnalysis } = await import('./api');
    mocks.get.mockResolvedValue({
      data: {
        product_id: 'P12',
        product_title: 'Kelto Gamer 16',
        total_reviews: 95,
        average_rating: 3.55,
      },
    });

    const controller = new AbortController();
    const result = await getProductAnalysis('P12', controller.signal);

    expect(result.product_id).toBe('P12');
    expect(mocks.get).toHaveBeenCalledWith(
      '/api/products/P12/analysis',
      expect.objectContaining({
        timeout: 45000,
        signal: controller.signal,
      })
    );
  });

  it('D2. searchProducts uses responsive search timeout (6000ms)', async () => {
    const { searchProducts } = await import('./api');
    mocks.get.mockResolvedValue({
      data: {
        found: true,
        products: [{ product_id: 'P12', product_title: 'Kelto Gamer 16' }],
      },
    });

    const result = await searchProducts('Kelto');
    expect(result.products).toHaveLength(1);
    expect(mocks.get).toHaveBeenCalledWith(
      '/api/products/search',
      expect.objectContaining({
        params: { q: 'Kelto', limit: 20 },
        timeout: 6000,
      })
    );
  });

  it('D3. handles timeout error in getProductAnalysis gracefully', async () => {
    const { getProductAnalysis } = await import('./api');
    mocks.get.mockRejectedValue(
      makeAxiosError({
        code: 'ECONNABORTED',
        message: 'timeout of 45000ms exceeded',
      })
    );

    await expect(getProductAnalysis('P12')).rejects.toThrow(
      'Request timed out. The AI model is taking longer than expected.'
    );
  });
});

