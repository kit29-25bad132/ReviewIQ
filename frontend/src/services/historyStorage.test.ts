import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { ReviewAnalysis } from '../types/review';

const mockState = vi.hoisted(() => ({
  configured: true,
  configError: null as string | null,
  insertPayload: null as Record<string, unknown> | null,
  insertData: null as Record<string, unknown> | null,
  insertError: null as Record<string, unknown> | null,
  selectData: null as unknown[] | null,
  selectError: null as Record<string, unknown> | null,
  selectThrow: false,
  deleteError: null as Record<string, unknown> | null,
  deleteCalls: [] as Array<{ type: 'eq' | 'neq'; value: string }>,
}));

vi.mock('./supabase', () => {
  const client = {
    from: (_table: string) => ({
      insert: (payload: Record<string, unknown>) => {
        mockState.insertPayload = payload;
        return {
          select: (_columns?: string) => ({
            single: async () => ({
              data: mockState.insertData,
              error: mockState.insertError,
            }),
          }),
        };
      },
      select: () => ({
        order: async () => {
          if (mockState.selectThrow) {
            throw new Error('network failure');
          }
          return {
            data: mockState.selectData,
            error: mockState.selectError,
          };
        },
      }),
      delete: () => ({
        eq: async (_column: string, value: string) => {
          mockState.deleteCalls.push({ type: 'eq', value });
          return { error: mockState.deleteError };
        },
        neq: async (_column: string, value: string) => {
          mockState.deleteCalls.push({ type: 'neq', value });
          return { error: mockState.deleteError };
        },
      }),
    }),
  };

  return {
    get supabase() {
      return mockState.configured ? client : null;
    },
    get isSupabaseConfigured() {
      return mockState.configured;
    },
    get supabaseConfigurationError() {
      return mockState.configError;
    },
  };
});

import {
  clearAllReviews,
  deleteReviewById,
  fetchAllReviews,
  getLocalReviews,
  saveReviewAnalysis,
  setLocalReviews,
  SupabasePersistenceError,
} from './historyStorage';

class MemoryStorage {
  private store = new Map<string, string>();

  getItem(key: string): string | null {
    return this.store.has(key) ? (this.store.get(key) as string) : null;
  }

  setItem(key: string, value: string): void {
    this.store.set(key, String(value));
  }

  removeItem(key: string): void {
    this.store.delete(key);
  }

  clear(): void {
    this.store.clear();
  }
}

const fullAnalysis: ReviewAnalysis = {
  sentiment: 'mixed',
  rating: 4,
  rating_source: 'explicit',
  summary: 'Great camera, weak battery.',
  aspects: [
    { aspect: 'camera', sentiment: 'positive', evidence: 'camera is excellent' },
    { aspect: 'battery', sentiment: 'negative', evidence: 'battery life is poor' },
    { aspect: 'display', sentiment: 'positive', evidence: 'display looks beautiful' },
  ],
  pros: [
    { point: 'Excellent camera', evidence: 'camera is excellent' },
    { point: 'Beautiful display', evidence: 'display looks beautiful' },
  ],
  cons: [{ point: 'Poor battery life', evidence: 'battery life is poor' }],
};

const reviewText = 'The camera is excellent but battery life is poor. 4 stars.';

const dbRowFrom = (analysis: ReviewAnalysis, overrides: Record<string, unknown> = {}) => ({
  id: 'row-1',
  review_text: reviewText,
  sentiment: analysis.sentiment,
  rating: analysis.rating,
  rating_source: analysis.rating_source,
  pros: analysis.pros,
  cons: analysis.cons,
  aspects: analysis.aspects,
  summary: analysis.summary,
  created_at: '2026-09-24T12:00:00.000Z',
  ...overrides,
});

const insertEchoRow = (analysis: ReviewAnalysis, overrides: Record<string, unknown> = {}) =>
  dbRowFrom(analysis, { id: 'saved-1', ...overrides });

beforeEach(() => {
  vi.stubGlobal('localStorage', new MemoryStorage());
  mockState.configured = true;
  mockState.configError = null;
  mockState.insertPayload = null;
  mockState.insertData = null;
  mockState.insertError = null;
  mockState.selectData = null;
  mockState.selectError = null;
  mockState.selectThrow = false;
  mockState.deleteError = null;
  mockState.deleteCalls = [];
  vi.spyOn(console, 'error').mockImplementation(() => {});
  vi.spyOn(console, 'warn').mockImplementation(() => {});
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('A. Full persistence round-trip', () => {
  it('persists and reloads every ReviewAnalysis field unchanged', async () => {
    mockState.insertData = insertEchoRow(fullAnalysis);
    mockState.selectData = [dbRowFrom(fullAnalysis)];

    const saved = await saveReviewAnalysis(reviewText, fullAnalysis);
    expect(saved.analysis).toEqual(fullAnalysis);
    expect(mockState.insertPayload).toMatchObject({
      review_text: reviewText,
      sentiment: 'mixed',
      rating: 4,
      rating_source: 'explicit',
      aspects: fullAnalysis.aspects,
      pros: fullAnalysis.pros,
      cons: fullAnalysis.cons,
      summary: fullAnalysis.summary,
    });

    const { reviews, source } = await fetchAllReviews();
    expect(source).toBe('supabase');
    expect(reviews).toHaveLength(1);
    expect(reviews[0].analysis).toEqual(fullAnalysis);
    expect(reviews[0].reviewText).toBe(reviewText);
    expect(reviews[0].createdAt).toBe('2026-09-24T12:00:00.000Z');
  });
});

describe('B. Rating source', () => {
  it.each(['explicit', 'inferred', 'not_found'] as const)('restores %s', async (source) => {
    const analysis: ReviewAnalysis = {
      ...fullAnalysis,
      rating: source === 'not_found' ? null : 4,
      rating_source: source,
    };
    mockState.insertData = insertEchoRow(analysis);
    mockState.selectData = [dbRowFrom(analysis)];

    await saveReviewAnalysis(reviewText, analysis);
    const { reviews } = await fetchAllReviews();
    expect(reviews[0].analysis.rating_source).toBe(source);
    expect(reviews[0].analysis.rating).toBe(analysis.rating);
  });
});

describe('C. Aspects', () => {
  it('does not replace multiple aspects with [] after reload', async () => {
    mockState.insertData = insertEchoRow(fullAnalysis);
    mockState.selectData = [dbRowFrom(fullAnalysis)];

    await saveReviewAnalysis(reviewText, fullAnalysis);
    const { reviews } = await fetchAllReviews();
    expect(reviews[0].analysis.aspects).toHaveLength(3);
    expect(reviews[0].analysis.aspects).toEqual(fullAnalysis.aspects);
  });
});

describe('D. Pros/cons evidence', () => {
  it('keeps point and evidence through serialization', async () => {
    mockState.insertData = insertEchoRow(fullAnalysis);
    mockState.selectData = [
      dbRowFrom(fullAnalysis, {
        pros: JSON.stringify(fullAnalysis.pros),
        cons: JSON.stringify(fullAnalysis.cons),
      }),
    ];

    await saveReviewAnalysis(reviewText, fullAnalysis);
    const { reviews } = await fetchAllReviews();
    expect(reviews[0].analysis.pros).toEqual(fullAnalysis.pros);
    expect(reviews[0].analysis.cons).toEqual(fullAnalysis.cons);
  });
});

describe('E. Legacy data', () => {
  it('normalizes legacy Supabase rows missing rating_source and aspects', async () => {
    mockState.selectData = [
      {
        id: 'legacy-1',
        review_text: 'Nice product',
        sentiment: 'positive',
        rating: 5,
        pros: ['Great value'],
        cons: '["Broken hinge"]',
        summary: 'Positive review',
        created_at: '2025-01-01T00:00:00.000Z',
      },
    ];

    const { reviews, source } = await fetchAllReviews();
    expect(source).toBe('supabase');
    expect(reviews[0].analysis.rating_source).toBe('inferred');
    expect(reviews[0].analysis.aspects).toEqual([]);
    expect(reviews[0].analysis.pros).toEqual([{ point: 'Great value', evidence: '' }]);
    expect(reviews[0].analysis.cons).toEqual([{ point: 'Broken hinge', evidence: '' }]);
  });

  it('normalizes legacy Supabase rows with null rating to not_found', async () => {
    mockState.selectData = [
      {
        id: 'legacy-null',
        review_text: 'No stars mentioned',
        sentiment: 'neutral',
        rating: null,
        pros: [],
        cons: [],
        summary: 'No rating',
        created_at: '2025-01-01T00:00:00.000Z',
      },
    ];

    const { reviews } = await fetchAllReviews();
    expect(reviews[0].analysis.rating).toBeNull();
    expect(reviews[0].analysis.rating_source).toBe('not_found');
  });

  it('normalizes legacy localStorage rows safely', () => {
    setLocalReviews([
      {
        id: 'local-legacy',
        reviewText: 'Old row',
        analysis: {
          sentiment: 'positive',
          rating: 5,
          rating_source: 'explicit',
          summary: 'ok',
          aspects: [{ aspect: 'battery', sentiment: 'positive', evidence: 'ok' }],
          pros: ['good'],
          cons: ['bad'],
        } as unknown as ReviewAnalysis,
        createdAt: '2025-01-01T00:00:00.000Z',
      },
      {
        id: 'broken',
        reviewText: 'ok',
        analysis: fullAnalysis,
        createdAt: 'bad',
      },
    ]);

    const items = getLocalReviews();
    expect(items).toHaveLength(2);
    expect(items[0].analysis.pros).toEqual([{ point: 'good', evidence: '' }]);
    expect(items[0].analysis.cons).toEqual([{ point: 'bad', evidence: '' }]);
    expect(items[0].analysis.aspects).toHaveLength(1);
    expect(items[0].analysis.rating_source).toBe('explicit');
    expect(typeof items[1].createdAt).toBe('string');
  });

  it('returns [] for corrupt localStorage JSON', () => {
    localStorage.setItem('product_review_analyzer_history_v1', '{not-json');
    expect(getLocalReviews()).toEqual([]);
  });
});

describe('F. Supabase unavailable/unconfigured', () => {
  it('falls back to localStorage when unconfigured', async () => {
    mockState.configured = false;
    mockState.configError = 'Supabase is not configured.';

    const saved = await saveReviewAnalysis(reviewText, fullAnalysis);
    expect(saved.analysis).toEqual(fullAnalysis);
    expect(getLocalReviews()).toHaveLength(1);

    const { reviews, source } = await fetchAllReviews();
    expect(source).toBe('local');
    expect(reviews[0].analysis).toEqual(fullAnalysis);
  });
});

describe('G. Supabase fetch failure', () => {
  it('does not destroy local history when cloud fetch fails', async () => {
    setLocalReviews([
      {
        id: 'local-keep',
        reviewText: 'Keep me',
        analysis: fullAnalysis,
        createdAt: '2026-01-01T00:00:00.000Z',
      },
    ]);
    mockState.selectData = null;
    mockState.selectError = { code: '500', message: 'internal error', details: '', hint: '' };

    const { reviews, source } = await fetchAllReviews();
    expect(source).toBe('local');
    expect(reviews).toHaveLength(1);
    expect(reviews[0].id).toBe('local-keep');
    expect(getLocalReviews()).toHaveLength(1);
  });

  it('does not destroy local history when cloud fetch throws', async () => {
    setLocalReviews([
      {
        id: 'local-keep-2',
        reviewText: 'Keep me too',
        analysis: fullAnalysis,
        createdAt: '2026-01-01T00:00:00.000Z',
      },
    ]);
    mockState.selectThrow = true;

    const { reviews, source } = await fetchAllReviews();
    expect(source).toBe('local');
    expect(reviews).toHaveLength(1);
    expect(reviews[0].id).toBe('local-keep-2');
    expect(getLocalReviews()[0].id).toBe('local-keep-2');
  });
});

describe('H. Insert failure', () => {
  it('surfaces Supabase insert errors as SupabasePersistenceError', async () => {
    mockState.insertData = null;
    mockState.insertError = {
      code: '42501',
      message: 'permission denied for table reviews',
      details: null,
      hint: null,
    };

    await expect(saveReviewAnalysis(reviewText, fullAnalysis)).rejects.toBeInstanceOf(
      SupabasePersistenceError
    );
    expect(getLocalReviews()).toHaveLength(0);
  });
});

describe('I. Delete failure', () => {
  it('detects Supabase delete errors and keeps local row', async () => {
    setLocalReviews([
      {
        id: 'del-1',
        reviewText: 'x',
        analysis: fullAnalysis,
        createdAt: '2026-01-01T00:00:00.000Z',
      },
    ]);
    mockState.deleteError = {
      code: '42501',
      message: 'permission denied',
      details: '',
      hint: '',
    };

    await expect(deleteReviewById('del-1')).rejects.toBeInstanceOf(SupabasePersistenceError);
    expect(getLocalReviews()).toHaveLength(1);
    expect(mockState.deleteCalls).toContainEqual({ type: 'eq', value: 'del-1' });
  });

  it('removes local row when Supabase delete succeeds', async () => {
    setLocalReviews([
      {
        id: 'del-2',
        reviewText: 'x',
        analysis: fullAnalysis,
        createdAt: '2026-01-01T00:00:00.000Z',
      },
    ]);
    mockState.deleteError = null;

    await deleteReviewById('del-2');
    expect(getLocalReviews()).toHaveLength(0);
  });
});

describe('J. Clear failure', () => {
  it('detects Supabase clear errors and keeps local rows', async () => {
    setLocalReviews([
      {
        id: 'keep-clear',
        reviewText: 'x',
        analysis: fullAnalysis,
        createdAt: '2026-01-01T00:00:00.000Z',
      },
    ]);
    mockState.deleteError = {
      code: 'PGRST116',
      message: 'delete failed',
      details: '',
      hint: '',
    };

    await expect(clearAllReviews()).rejects.toBeInstanceOf(SupabasePersistenceError);
    expect(getLocalReviews()).toHaveLength(1);
    expect(mockState.deleteCalls.some((c) => c.type === 'neq')).toBe(true);
  });

  it('clears local history when Supabase clear succeeds', async () => {
    setLocalReviews([
      {
        id: 'cleared',
        reviewText: 'x',
        analysis: fullAnalysis,
        createdAt: '2026-01-01T00:00:00.000Z',
      },
    ]);
    mockState.deleteError = null;

    await clearAllReviews();
    expect(getLocalReviews()).toHaveLength(0);
  });
});

describe('Cache fidelity', () => {
  it('cloud snapshot cache retains rating_source, aspects, and evidence', async () => {
    mockState.selectData = [dbRowFrom(fullAnalysis)];

    const { reviews } = await fetchAllReviews();
    const cached = getLocalReviews();
    expect(cached).toHaveLength(1);
    expect(cached[0].analysis).toEqual(reviews[0].analysis);
    expect(cached[0].analysis.rating_source).toBe('explicit');
    expect(cached[0].analysis.aspects).toHaveLength(3);
    expect(cached[0].analysis.pros[0].evidence).toBe('camera is excellent');
  });
});
