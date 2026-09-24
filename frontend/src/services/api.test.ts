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
    response?: { status: number; data?: unknown };
    code?: string;
    request?: unknown;
  } = {}
) => {
  const error = Object.assign(new Error('Request failed with status code'), {
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
    expect(mocks.post).toHaveBeenCalledWith('/api/analyze-review', {
      review: 'The camera is excellent but battery life is poor. 4 stars.',
    });
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

  it('B3. timeout maps to a safe timeout message', async () => {
    mocks.post.mockRejectedValue(
      makeAxiosError({
        code: 'ECONNABORTED',
      })
    );

    await expect(analyzeReview('slow')).rejects.toThrow(
      'Request timed out. The AI model is taking longer than expected.'
    );
  });

  it('B4. network failure without response surfaces offline message including base URL', async () => {
    mocks.post.mockRejectedValue(
      makeAxiosError({
        request: {},
      })
    );

    await expect(analyzeReview('x')).rejects.toThrow(/Backend Offline: Cannot connect/);
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
