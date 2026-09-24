import { ReviewAnalysis, ReviewHistoryItem } from '../types/review';
import {
  supabase,
  isSupabaseConfigured,
  supabaseConfigurationError,
} from './supabase';

const LOCAL_STORAGE_KEY = 'product_review_analyzer_history_v1';

type SupabaseErrorFields = {
  code: string;
  message: string;
  details: string;
  hint: string;
};

type ReviewsTableRow = {
  id: string;
  review_text: string;
  sentiment: ReviewAnalysis['sentiment'];
  rating: number;
  pros: unknown;
  cons: unknown;
  summary: string;
  created_at: string;
};

const normalizeSupabaseError = (error: unknown): SupabaseErrorFields => {
  const record =
    typeof error === 'object' && error !== null
      ? (error as Record<string, unknown>)
      : {};

  const code = typeof record.code === 'string' && record.code.trim()
    ? record.code.trim()
    : 'UNKNOWN';
  const message = typeof record.message === 'string' && record.message.trim()
    ? record.message.trim()
    : error instanceof Error
      ? error.message
      : String(error);
  const details = record.details === null || record.details === undefined
    ? ''
    : String(record.details);
  const hint = record.hint === null || record.hint === undefined
    ? ''
    : String(record.hint);

  return { code, message, details, hint };
};

const formatSupabaseError = (operation: string, fields: SupabaseErrorFields): string => {
  const parts = [
    `Supabase ${operation} failed`,
    `code: ${fields.code}`,
    `message: ${fields.message}`,
  ];

  if (fields.details) parts.push(`details: ${fields.details}`);
  if (fields.hint) parts.push(`hint: ${fields.hint}`);

  return parts.join(' | ');
};

const logSupabaseError = (operation: string, error: unknown): SupabaseErrorFields => {
  const fields = normalizeSupabaseError(error);
  console.error(`Supabase ${operation} error`, {
    code: fields.code || null,
    message: fields.message,
    details: fields.details || null,
    hint: fields.hint || null,
  });
  return fields;
};

export class SupabasePersistenceError extends Error {
  readonly code: string;
  readonly details: string;
  readonly hint: string;

  constructor(operation: string, fields: SupabaseErrorFields) {
    super(formatSupabaseError(operation, fields));
    this.name = 'SupabasePersistenceError';
    this.code = fields.code;
    this.details = fields.details;
    this.hint = fields.hint;
  }
}

const createSupabasePersistenceError = (
  operation: string,
  error: unknown
): SupabasePersistenceError => new SupabasePersistenceError(operation, logSupabaseError(operation, error));

// Read from LocalStorage cache
export const getLocalReviews = (): ReviewHistoryItem[] => {
  try {
    const raw = localStorage.getItem(LOCAL_STORAGE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
};

// Write to LocalStorage cache
export const setLocalReviews = (items: ReviewHistoryItem[]): void => {
  try {
    localStorage.setItem(LOCAL_STORAGE_KEY, JSON.stringify(items));
  } catch (err) {
    console.error('Failed to save to localStorage:', err);
  }
};

const parseReviewList = (value: unknown): string[] => {
  let parsedValue: unknown = value;

  if (typeof value === 'string') {
    try {
      parsedValue = JSON.parse(value);
    } catch {
      return [];
    }
  }

  if (!Array.isArray(parsedValue)) return [];

  return parsedValue.filter((item): item is string => typeof item === 'string');
};

const createLocalReview = (
  reviewText: string,
  analysis: ReviewAnalysis
): ReviewHistoryItem => {
  const localId =
    typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function'
      ? crypto.randomUUID()
      : Date.now().toString();

  return {
    id: localId,
    reviewText,
    analysis,
    createdAt: new Date().toISOString(),
  };
};

const cacheReview = (review: ReviewHistoryItem): void => {
  const currentLocal = getLocalReviews();
  const updated = [review, ...currentLocal.filter((item) => item.id !== review.id)];
  setLocalReviews(updated);
};

const formatReviewRow = (row: ReviewsTableRow): ReviewHistoryItem => ({
  id: row.id,
  reviewText: row.review_text,
  analysis: {
    sentiment: row.sentiment,
    rating: row.rating,
    pros: parseReviewList(row.pros),
    cons: parseReviewList(row.cons),
    summary: row.summary,
  },
  createdAt: row.created_at,
});

/**
 * Fetch all reviews from Supabase (or fallback to localStorage).
 */
export async function fetchAllReviews(): Promise<{ reviews: ReviewHistoryItem[]; source: 'supabase' | 'local' }> {
  if (isSupabaseConfigured && supabase) {
    try {
      const { data, error } = await supabase
        .from('reviews')
        .select('*')
        .order('created_at', { ascending: false });

      if (error) {
        logSupabaseError('fetch', error);
        return { reviews: getLocalReviews(), source: 'local' };
      }

      if (data) {
        const formatted = data.map((row: ReviewsTableRow) => formatReviewRow(row));

        // Sync local cache with the successfully fetched database snapshot.
        setLocalReviews(formatted);
        return { reviews: formatted, source: 'supabase' };
      }
    } catch (error) {
      logSupabaseError('fetch exception', error);
    }
  }

  return { reviews: getLocalReviews(), source: 'local' };
}

/**
 * Save a new validated review analysis to Supabase, then cache the returned row.
 * When Supabase is not configured, the existing local-only mode remains available
 * and is explicitly reported by the configuration banner in the dashboard.
 */
export async function saveReviewAnalysis(
  reviewText: string,
  analysis: ReviewAnalysis
): Promise<ReviewHistoryItem> {
  const client = supabase;

  if (!isSupabaseConfigured || !client) {
    const localReview = createLocalReview(reviewText, analysis);
    cacheReview(localReview);

    console.warn('Supabase insert skipped because the client is not configured', {
      code: 'SUPABASE_NOT_CONFIGURED',
      message: supabaseConfigurationError || 'Supabase client is unavailable.',
      details: null,
      hint: 'Set VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY (or VITE_SUPABASE_PUBLISHABLE_KEY), then restart or rebuild the frontend.',
    });

    return localReview;
  }

  try {
    const insertPayload = {
      review_text: reviewText,
      sentiment: analysis.sentiment,
      rating: analysis.rating,
      pros: analysis.pros,
      cons: analysis.cons,
      summary: analysis.summary,
    };

    const { data, error } = await client
      .from('reviews')
      .insert(insertPayload)
      .select('id, review_text, sentiment, rating, pros, cons, summary, created_at')
      .single();

    if (error) {
      throw createSupabasePersistenceError('insert', error);
    }

    if (!data || typeof data.id !== 'string' || data.id.length === 0) {
      throw createSupabasePersistenceError('insert', {
        code: 'INSERT_NO_ROW',
        message: 'Supabase accepted the insert request but did not return the inserted row.',
        details: null,
        hint: 'Check the INSERT policy and the returned row from PostgREST.',
      });
    }

    const savedReview: ReviewHistoryItem = {
      id: data.id,
      reviewText: data.review_text ?? reviewText,
      analysis: {
        sentiment: data.sentiment ?? analysis.sentiment,
        rating: data.rating ?? analysis.rating,
        pros: data.pros === undefined ? analysis.pros : parseReviewList(data.pros),
        cons: data.cons === undefined ? analysis.cons : parseReviewList(data.cons),
        summary: data.summary ?? analysis.summary,
      },
      createdAt: data.created_at ?? new Date().toISOString(),
    };

    cacheReview(savedReview);
    return savedReview;
  } catch (error) {
    if (error instanceof SupabasePersistenceError) {
      throw error;
    }

    throw createSupabasePersistenceError('insert exception', error);
  }
}

/**
 * Delete a review from Supabase & localStorage.
 */
export async function deleteReviewById(id: string): Promise<void> {
  if (isSupabaseConfigured && supabase) {
    try {
      await supabase.from('reviews').delete().eq('id', id);
    } catch (err) {
      console.warn('Supabase delete exception:', err);
    }
  }

  const current = getLocalReviews();
  const updated = current.filter((item) => item.id !== id);
  setLocalReviews(updated);
}

/**
 * Clear all history from Supabase & localStorage.
 */
export async function clearAllReviews(): Promise<void> {
  if (isSupabaseConfigured && supabase) {
    try {
      await supabase.from('reviews').delete().neq('id', '00000000-0000-0000-0000-000000000000');
    } catch (err) {
      console.warn('Supabase clear exception:', err);
    }
  }

  setLocalReviews([]);
}
