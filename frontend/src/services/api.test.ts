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

import { analyzeReview, askProductQuestion } from './api';

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

describe('askProductQuestion (Phase 7 rag-query client)', () => {
  const groundedResponse = {
    answer: 'Battery lasts two days. [R00669].',
    evidence: [
      {
        review_id: 'R00669',
        excerpt: 'the battery life is okay',
        similarity_score: 0.72,
        rating: 4,
      },
    ],
    retrieval_count: 1,
    context_token_estimate: 42,
    model_used: 'gemini-2.0-flash',
    rag_enabled: true,
    fallback_used: false,
  };

  it('A. posts to the per-product rag-query endpoint with the query verbatim', async () => {
    mocks.post.mockResolvedValue({ data: groundedResponse });

    await askProductQuestion('P12', '  how is the battery life?  ');

    // Verbatim pass-through: never trimmed or rewritten (backend contract
    // rejects whitespace-only input itself with 422).
    expect(mocks.post).toHaveBeenCalledWith(
      '/api/products/P12/rag-query',
      { query: '  how is the battery life?  ' },
      expect.objectContaining({ timeout: 45000 })
    );
  });

  it('B. returns every grounded response field unchanged, including evidence and empty-answer flags', async () => {
    mocks.post.mockResolvedValue({ data: groundedResponse });

    const result = await askProductQuestion('P12', 'how is the battery life?');

    expect(result).toEqual(groundedResponse);
    expect(result.answer).toBe('Battery lasts two days. [R00669].');
    expect(result.evidence).toHaveLength(1);
    expect(result.rag_enabled).toBe(true);

    // Legitimate empty answers (disabled / empty retrieval / discarded) pass
    // through untouched — the client must never fabricate content for them.
    mocks.post.mockResolvedValue({
      data: {
        answer: '',
        evidence: [],
        retrieval_count: 0,
        context_token_estimate: 0,
        model_used: '',
        rag_enabled: true,
        fallback_used: false,
      },
    });
    const empty = await askProductQuestion('P12', 'off topic question');
    expect(empty.answer).toBe('');
    expect(empty.evidence).toEqual([]);
  });

  it('C. surfaces a readable message from the real FastAPI array-shaped 422 detail', async () => {
    mocks.post.mockRejectedValue(
      makeAxiosError({
        response: {
          status: 422,
          data: {
            detail: [
              {
                type: 'value_error',
                loc: ['body', 'query'],
                msg: 'Value error, query must contain at least one non-whitespace character',
                input: '   ',
              },
            ],
          },
        },
      })
    );

    await expect(askProductQuestion('P12', '   ')).rejects.toThrow(
      'Value error, query must contain at least one non-whitespace character'
    );
  });

  it('C2. keeps plain-string validation details working unchanged', async () => {
    mocks.post.mockRejectedValue(
      makeAxiosError({
        response: {
          status: 422,
          data: {
            detail: 'query must contain at least one non-whitespace character.',
          },
        },
      })
    );

    await expect(askProductQuestion('P12', '   ')).rejects.toThrow(
      'query must contain at least one non-whitespace character.'
    );
  });

  it('C3. malformed or empty validation details fall back safely without [object Object]', async () => {
    const malformedPayloads: Array<Record<string, unknown>> = [
      { detail: {} },
      { detail: [] },
      { detail: [{ nope: true }] },
      { detail: [{ msg: '' }] },
      {},
    ];

    for (const data of malformedPayloads) {
      mocks.post.mockRejectedValue(
        makeAxiosError({ response: { status: 422, data } })
      );

      const err = await askProductQuestion('P12', '   ').catch((e: unknown) => e);
      expect(err).toBeInstanceOf(Error);
      const message = (err as Error).message;
      expect(message).not.toContain('[object Object]');
      expect(message.length).toBeGreaterThan(0);
    }
  });

  it('D. reports timeouts through the shared API error contract', async () => {
    mocks.post.mockRejectedValue(
      makeAxiosError({
        code: 'ECONNABORTED',
        message: 'timeout of 45000ms exceeded',
      })
    );

    await expect(askProductQuestion('P12', 'battery life?')).rejects.toThrow(
      'Request timed out. The AI model is taking longer than expected.'
    );
  });
});

