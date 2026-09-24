import {
  AspectSentiment,
  PointEvidence,
  RatingSource,
  ReviewAnalysis,
  ReviewHistoryItem,
  SentimentType,
} from '../types/review';
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
  rating: number | null;
  pros: unknown;
  cons: unknown;
  aspects?: unknown;
  summary: string;
  created_at: string;
  rating_source?: string | null;
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

// Read from LocalStorage cache (normalizes legacy rows to the current contract)
export const getLocalReviews = (): ReviewHistoryItem[] => {
  try {
    const raw = localStorage.getItem(LOCAL_STORAGE_KEY);
    if (!raw) return [];
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed
      .map(normalizeHistoryItem)
      .filter((item): item is ReviewHistoryItem => item !== null);
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

const isPointEvidence = (item: unknown): item is PointEvidence =>
  typeof item === 'object' &&
  item !== null &&
  typeof (item as PointEvidence).point === 'string' &&
  typeof (item as PointEvidence).evidence === 'string';

/**
 * Deserialize pros/cons while preserving PointEvidence {point, evidence}.
 * Legacy plain-string rows are converted to {point, evidence: ''} rather than
 * dropped; evidence stays a string (never re-flattened into a single string).
 */
const parsePointEvidenceList = (value: unknown): PointEvidence[] => {
  let parsedValue: unknown = value;

  if (typeof value === 'string') {
    try {
      parsedValue = JSON.parse(value);
    } catch {
      return [];
    }
  }

  if (!Array.isArray(parsedValue)) return [];

  return parsedValue.flatMap((item): PointEvidence[] => {
    if (typeof item === 'string') {
      return item.trim() ? [{ point: item, evidence: '' }] : [];
    }
    if (isPointEvidence(item)) {
      return [{ point: item.point, evidence: item.evidence }];
    }
    if (
      typeof item === 'object' &&
      item !== null &&
      typeof (item as PointEvidence).point === 'string'
    ) {
      const partial = item as Partial<PointEvidence>;
      return [{ point: partial.point as string, evidence: '' }];
    }
    return [];
  });
};

const isSentiment = (value: unknown): value is SentimentType =>
  value === 'positive' || value === 'negative' || value === 'neutral' || value === 'mixed';

const isAspectSentiment = (item: unknown): item is AspectSentiment =>
  typeof item === 'object' &&
  item !== null &&
  typeof (item as AspectSentiment).aspect === 'string' &&
  isSentiment((item as AspectSentiment).sentiment) &&
  typeof (item as AspectSentiment).evidence === 'string';

/**
 * Deserialize AspectSentiment[] from JSONB / JSON string / legacy rows.
 * Returns [] only when the value is missing or not a valid aspect list.
 */
const parseAspects = (value: unknown): AspectSentiment[] => {
  let parsedValue: unknown = value;

  if (typeof value === 'string') {
    try {
      parsedValue = JSON.parse(value);
    } catch {
      return [];
    }
  }

  if (!Array.isArray(parsedValue)) return [];

  return parsedValue.filter(isAspectSentiment);
};

const deriveRatingSource = (
  row: Pick<ReviewsTableRow, 'rating' | 'rating_source'>
): RatingSource => {
  if (typeof row.rating_source === 'string') {
    const source = row.rating_source as RatingSource;
    if (source === 'explicit' || source === 'inferred' || source === 'not_found') {
      return source;
    }
  }
  return row.rating === null ? 'not_found' : 'inferred';
};

const normalizeSentiment = (value: unknown): ReviewAnalysis['sentiment'] =>
  value === 'positive' || value === 'negative' || value === 'neutral' || value === 'mixed'
    ? value
    : 'neutral';

const normalizeRating = (value: unknown): number | null =>
  typeof value === 'number' && Number.isInteger(value) && value >= 1 && value <= 5
    ? value
    : null;

/** Coerce older localStorage rows (string pros/cons, missing new fields) to the current contract. */
const normalizeStoredAnalysis = (value: unknown): ReviewAnalysis => {
  const raw = (typeof value === 'object' && value !== null ? value : {}) as Partial<ReviewAnalysis>;
  const rating = normalizeRating(raw.rating);
  return {
    sentiment: normalizeSentiment(raw.sentiment),
    rating,
    rating_source:
      raw.rating_source === 'explicit' ||
      raw.rating_source === 'inferred' ||
      raw.rating_source === 'not_found'
        ? raw.rating_source
        : rating === null
          ? 'not_found'
          : 'inferred',
    summary: typeof raw.summary === 'string' ? raw.summary : '',
    aspects: parseAspects(raw.aspects),
    pros: parsePointEvidenceList(raw.pros),
    cons: parsePointEvidenceList(raw.cons),
  };
};

const normalizeHistoryItem = (value: unknown): ReviewHistoryItem | null => {
  if (typeof value !== 'object' || value === null) return null;
  const raw = value as Partial<ReviewHistoryItem>;
  if (typeof raw.id !== 'string' || typeof raw.reviewText !== 'string') return null;
  return {
    id: raw.id,
    reviewText: raw.reviewText,
    analysis: normalizeStoredAnalysis(raw.analysis),
    createdAt:
      typeof raw.createdAt === 'string' ? raw.createdAt : new Date().toISOString(),
  };
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
    rating: row.rating ?? null,
    rating_source: deriveRatingSource(row),
    summary: row.summary,
    aspects: parseAspects(row.aspects),
    pros: parsePointEvidenceList(row.pros),
    cons: parsePointEvidenceList(row.cons),
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
      rating_source: analysis.rating_source,
      pros: analysis.pros,
      cons: analysis.cons,
      aspects: analysis.aspects,
      summary: analysis.summary,
    };

    const { data, error } = await client
      .from('reviews')
      .insert(insertPayload)
      .select(
        'id, review_text, sentiment, rating, rating_source, pros, cons, aspects, summary, created_at'
      )
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

    const returnedRating =
      data.rating !== undefined ? data.rating : analysis.rating;
    const returnedRatingSource = (data as { rating_source?: string | null })
      .rating_source;
    const returnedAspects = (data as { aspects?: unknown }).aspects;

    const savedReview: ReviewHistoryItem = {
      id: data.id,
      reviewText: data.review_text ?? reviewText,
      analysis: {
        sentiment: data.sentiment ?? analysis.sentiment,
        rating: returnedRating,
        rating_source:
          returnedRatingSource === 'explicit' ||
          returnedRatingSource === 'inferred' ||
          returnedRatingSource === 'not_found'
            ? returnedRatingSource
            : analysis.rating_source,
        pros:
          data.pros === undefined
            ? analysis.pros
            : parsePointEvidenceList(data.pros),
        cons:
          data.cons === undefined
            ? analysis.cons
            : parsePointEvidenceList(data.cons),
        aspects:
          returnedAspects === undefined
            ? analysis.aspects
            : parseAspects(returnedAspects),
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
 * Supabase failures are inspected and thrown (not treated as success);
 * localStorage is only updated when the cloud delete succeeds or Supabase is unconfigured.
 */
export async function deleteReviewById(id: string): Promise<void> {
  if (isSupabaseConfigured && supabase) {
    try {
      const { error } = await supabase.from('reviews').delete().eq('id', id);
      if (error) {
        throw createSupabasePersistenceError('delete', error);
      }
    } catch (err) {
      if (err instanceof SupabasePersistenceError) {
        throw err;
      }
      throw createSupabasePersistenceError('delete exception', err);
    }
  }

  const current = getLocalReviews();
  const updated = current.filter((item) => item.id !== id);
  setLocalReviews(updated);
}

/**
 * Clear all history from Supabase & localStorage.
 * Supabase failures are inspected and thrown (not treated as success);
 * localStorage is only cleared when the cloud delete succeeds or Supabase is unconfigured.
 */
export async function clearAllReviews(): Promise<void> {
  if (isSupabaseConfigured && supabase) {
    try {
      const { error } = await supabase
        .from('reviews')
        .delete()
        .neq('id', '00000000-0000-0000-0000-000000000000');
      if (error) {
        throw createSupabasePersistenceError('clear', error);
      }
    } catch (err) {
      if (err instanceof SupabasePersistenceError) {
        throw err;
      }
      throw createSupabasePersistenceError('clear exception', err);
    }
  }

  setLocalReviews([]);
}
