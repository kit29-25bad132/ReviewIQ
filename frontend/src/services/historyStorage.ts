import { ReviewAnalysis, ReviewHistoryItem } from '../types/review';
import { supabase, isSupabaseConfigured } from './supabase';

const LOCAL_STORAGE_KEY = 'product_review_analyzer_history_v1';

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
        console.warn('Supabase fetch error, using local storage cache:', error.message);
        return { reviews: getLocalReviews(), source: 'local' };
      }

      if (data) {
        const formatted: ReviewHistoryItem[] = data.map((row: any) => ({
          id: row.id,
          reviewText: row.review_text,
          analysis: {
            sentiment: row.sentiment,
            rating: row.rating,
            pros: Array.isArray(row.pros) ? row.pros : JSON.parse(row.pros || '[]'),
            cons: Array.isArray(row.cons) ? row.cons : JSON.parse(row.cons || '[]'),
            summary: row.summary,
          },
          createdAt: row.created_at,
        }));

        // Sync local cache
        setLocalReviews(formatted);
        return { reviews: formatted, source: 'supabase' };
      }
    } catch (err) {
      console.warn('Supabase connection failed, using local storage:', err);
    }
  }

  return { reviews: getLocalReviews(), source: 'local' };
}

/**
 * Save a new review analysis to Supabase & localStorage.
 */
export async function saveReviewAnalysis(
  reviewText: string,
  analysis: ReviewAnalysis
): Promise<ReviewHistoryItem> {
  const localId = crypto.randomUUID ? crypto.randomUUID() : Date.now().toString();
  const createdAt = new Date().toISOString();

  let finalId = localId;

  if (isSupabaseConfigured && supabase) {
    try {
      const { data, error } = await supabase
        .from('reviews')
        .insert({
          review_text: reviewText,
          sentiment: analysis.sentiment,
          rating: analysis.rating,
          pros: analysis.pros,
          cons: analysis.cons,
          summary: analysis.summary,
        })
        .select()
        .single();

      if (error) {
        console.warn('Supabase insert failed, falling back to local ID:', error.message);
      } else if (data && data.id) {
        finalId = data.id;
      }
    } catch (err) {
      console.warn('Supabase insert exception:', err);
    }
  }

  const newItem: ReviewHistoryItem = {
    id: finalId,
    reviewText,
    analysis,
    createdAt,
  };

  const currentLocal = getLocalReviews();
  const updated = [newItem, ...currentLocal.filter((item) => item.id !== finalId)];
  setLocalReviews(updated);

  return newItem;
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
