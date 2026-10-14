import axios, { AxiosError } from 'axios';
import {
  AnalyzeReviewResponse,
  ReviewAnalysis,
  DatasetReviewsResponse,
  OverviewAnalytics,
  ProductAnalytics,
  EvaluationMetrics,
} from '../types/review';
import {
  ProductSearchResponse,
  ProductAnalysisResponse,
  ReviewsPaginationResponse,
  AISummaryResponse,
  ProsConsAnalysisResponse,
  ReviewItem,
  ProductSummary,
  UserRequirementRequest,
  PersonalizedRecommendationResponse,
  RAGQueryResponse,
} from '../types/ecommerce';
import {
  AnalysisErrorResponse,
  ProductIntelligence,
} from '../types/intelligence';

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';

// Configurable timeouts via environment variables
export const DEFAULT_TIMEOUT_MS = Number(import.meta.env.VITE_API_TIMEOUT_MS) || 10000;
export const AI_ANALYSIS_TIMEOUT_MS = Number(import.meta.env.VITE_AI_ANALYSIS_TIMEOUT_MS) || 45000;
export const SEARCH_TIMEOUT_MS = Number(import.meta.env.VITE_SEARCH_TIMEOUT_MS) || 6000;
export const EVALUATION_TIMEOUT_MS = Number(import.meta.env.VITE_EVALUATION_TIMEOUT_MS) || 180000;
// Phase 5 intelligence runs three grounded AI stages (aspects, RAG pros/cons,
// summary) plus a live similarity search, so it needs a much longer budget
// than the legacy single-shot analysis call.
export const INTELLIGENCE_TIMEOUT_MS =
  Number(import.meta.env.VITE_INTELLIGENCE_TIMEOUT_MS) || 240000;

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: DEFAULT_TIMEOUT_MS,
});

export interface HealthStatus {
  status: string;
  ai_configured: boolean;
  ai_provider: string;
}

/**
 * Extracts a human-readable message from an API error payload without ever
 * rendering `[object Object]`.
 *
 * FastAPI request-validation errors carry `detail` as an array of objects with
 * a `msg` field; other endpoints return `detail`/`error` as plain strings.
 * Missing, empty, malformed, or unexpected shapes return `null` so callers
 * fall back to their status-based messages.
 */
function formatApiErrorMessage(payload: unknown): string | null {
  if (typeof payload === 'string') {
    return payload.length > 0 ? payload : null;
  }
  if (Array.isArray(payload)) {
    const messages = payload
      .map((item): string | null => {
        if (item && typeof item === 'object' && 'msg' in item) {
          const msg = (item as { msg?: unknown }).msg;
          if (typeof msg === 'string' && msg.length > 0) {
            return msg;
          }
        }
        return null;
      })
      .filter((msg): msg is string => msg !== null);
    return messages.length > 0 ? messages.join(' ') : null;
  }
  return null;
}

/**
 * Formats API errors into descriptive, user-facing error messages.
 */
export function handleApiError(error: unknown, fallbackMessage = 'An unexpected error occurred.'): never {
  if (axios.isCancel?.(error)) {
    throw new Error('Request was cancelled.');
  }

  if (axios.isAxiosError(error)) {
    const axiosErr = error as AxiosError<{ detail?: unknown; error?: unknown }>;

    if (axiosErr.response) {
      const message =
        formatApiErrorMessage(axiosErr.response.data?.detail) ??
        formatApiErrorMessage(axiosErr.response.data?.error);
      if (message) {
        throw new Error(message);
      }
      if (axiosErr.response.status === 400) {
        throw new Error('Invalid review input. Please check the review text.');
      }
      if (axiosErr.response.status === 404) {
        throw new Error('The requested product or dataset was not found.');
      }
      if (axiosErr.response.status === 500) {
        throw new Error('AI analysis service encountered an error. Please try again.');
      }
    } else if (axiosErr.code === 'ECONNABORTED' || axiosErr.message?.toLowerCase().includes('timeout')) {
      throw new Error('Request timed out. The AI model is taking longer than expected.');
    } else if (axiosErr.request) {
      throw new Error(`Backend Offline: Cannot connect to FastAPI backend at ${API_BASE_URL}.`);
    }
  }

  throw new Error(error instanceof Error ? error.message : fallbackMessage);
}

function extractExplicitRating(text: string): number | null {
  const normalized = text.toLowerCase();
  const patterns = [
    /(\d)\s*(?:\/\s*5|out\s*of\s*5|stars?)/,
    /rating\s*[:=]?\s*(\d)/,
    /rated\s*(\d)\s*(?:out\s*of\s*5|stars?)/,
  ];

  for (const pattern of patterns) {
    const match = normalized.match(pattern);
    if (match) {
      const value = Number(match[1]);
      if (value >= 1 && value <= 5) {
        return value;
      }
    }
  }

  return null;
}

export function localReviewAnalysisFallback(reviewText: string): ReviewAnalysis {
  const text = (reviewText || '').trim();
  const lower = text.toLowerCase();
  const positiveWords = ['excellent', 'great', 'good', 'love', 'amazing', 'perfect', 'fast', 'smooth', 'beautiful', 'nice', 'clear', 'reliable', 'easy', 'helpful'];
  const negativeWords = ['bad', 'poor', 'terrible', 'slow', 'cheap', 'weak', 'broken', 'flimsy', 'disappointing', 'hot', 'buggy', 'loud', 'difficult', 'confusing', 'blurry', 'awful'];

  const explicitRating = extractExplicitRating(text);
  let rating = explicitRating ?? 3;
  let ratingSource: 'explicit' | 'inferred' | 'not_found' = explicitRating ? 'explicit' : 'inferred';

  if (!explicitRating) {
    const positiveCount = positiveWords.filter((word) => lower.includes(word)).length;
    const negativeCount = negativeWords.filter((word) => lower.includes(word)).length;

    if (positiveCount > negativeCount) rating = 4;
    else if (negativeCount > positiveCount) rating = 2;
    else rating = 3;
  }

  const hasPositive = positiveWords.some((word) => lower.includes(word));
  const hasNegative = negativeWords.some((word) => lower.includes(word));
  const sentiment: ReviewAnalysis['sentiment'] = hasPositive && hasNegative ? 'mixed' : hasPositive ? 'positive' : hasNegative ? 'negative' : 'neutral';

  const summary = text.length > 180 ? `${text.slice(0, 177).trim()}...` : text || 'Customer review indicates a clear experience based on the provided feedback.';

  const aspects: ReviewAnalysis['aspects'] = [
    { aspect: 'overall', sentiment, evidence: text || 'Review text was provided.' },
  ];

  const pros: ReviewAnalysis['pros'] = hasPositive
    ? [{ point: 'Positive experience noted', evidence: text }]
    : [];
  const cons: ReviewAnalysis['cons'] = hasNegative
    ? [{ point: 'Issues mentioned in the review', evidence: text }]
    : [];

  return {
    sentiment,
    rating,
    rating_source: ratingSource,
    summary,
    aspects,
    pros,
    cons,
  };
}

/**
 * Sends customer review to backend for AI analysis.
 */
export async function analyzeReview(reviewText: string, signal?: AbortSignal): Promise<ReviewAnalysis> {
  try {
    const response = await apiClient.post<AnalyzeReviewResponse>(
      '/api/analyze-review',
      { review: reviewText },
      { timeout: AI_ANALYSIS_TIMEOUT_MS, signal }
    );

    if (response.data && response.data.success && response.data.data) {
      return response.data.data;
    }

    throw new Error(response.data?.error || 'Failed to analyze review');
  } catch (error) {
    if (axios.isAxiosError(error)) {
      const axiosErr = error as AxiosError<{ detail?: string; error?: string }>;
      const isTimeout = axiosErr.code === 'ECONNABORTED' || axiosErr.message?.toLowerCase().includes('timeout');
      const isOffline = !axiosErr.response && !!axiosErr.request;
      if (isTimeout || isOffline) {
        return localReviewAnalysisFallback(reviewText);
      }
    }

    return handleApiError(error, 'An unknown error occurred while analyzing the review.');
  }
}

/**
 * Checks backend health and API configuration status.
 */
export async function checkBackendHealth(signal?: AbortSignal): Promise<HealthStatus> {
  try {
    const response = await apiClient.get<HealthStatus>('/health', { timeout: 4000, signal });
    return response.data;
  } catch {
    return {
      status: 'offline',
      ai_configured: false,
      ai_provider: 'Google Gemini',
    };
  }
}

/**
 * Searches products in the dataset with short, responsive timeout.
 */
export async function searchProducts(
  q: string,
  limit: number = 20,
  signal?: AbortSignal
): Promise<ProductSearchResponse> {
  try {
    const response = await apiClient.get<ProductSearchResponse>('/api/products/search', {
      params: { q: q.trim() || undefined, limit },
      timeout: SEARCH_TIMEOUT_MS,
      signal,
    });
    return response.data;
  } catch (error) {
    return handleApiError(error, 'Failed to search products.');
  }
}

/**
 * Retrieves complete canonical dataset statistics and grounded Gemini AI analysis for a product.
 */
export async function getProductAnalysis(
  productId: string,
  signal?: AbortSignal
): Promise<ProductAnalysisResponse> {
  try {
    const response = await apiClient.get<ProductAnalysisResponse>(
      `/api/products/${productId}/analysis`,
      {
        timeout: AI_ANALYSIS_TIMEOUT_MS,
        signal,
      }
    );
    return response.data;
  } catch (error) {
    return handleApiError(error, 'Failed to retrieve product intelligence.');
  }
}

/**
 * Explicitly requests complete grounded Gemini AI analysis and factual dataset metrics for a product.
 */
export async function analyzeProduct(
  productId: string,
  signal?: AbortSignal
): Promise<ProductAnalysisResponse> {
  try {
    const response = await apiClient.post<ProductAnalysisResponse>(
      `/api/products/${productId}/analyze`,
      {},
      {
        timeout: AI_ANALYSIS_TIMEOUT_MS,
        signal,
      }
    );
    return response.data;
  } catch (error) {
    return handleApiError(error, 'Failed to analyze product.');
  }
}

/**
 * Retrieves dynamic Pros & Cons with statistical review counts and percentages.
 */
export async function getProductProsCons(
  productId: string,
  signal?: AbortSignal
): Promise<ProsConsAnalysisResponse> {
  try {
    const response = await apiClient.get<ProsConsAnalysisResponse>(
      `/api/products/${productId}/pros-cons`,
      {
        timeout: DEFAULT_TIMEOUT_MS,
        signal,
      }
    );
    return response.data;
  } catch (error) {
    return handleApiError(error, 'Failed to fetch pros and cons.');
  }
}

/**
 * Retrieves actual supporting reviews for a specific Pro/Con theme from the dataset.
 */
export async function getThemeSupportingReviews(
  productId: string,
  theme: string,
  sentiment?: string,
  limit: number = 50,
  signal?: AbortSignal
): Promise<ReviewItem[]> {
  try {
    const response = await apiClient.get<ReviewItem[]>(
      `/api/products/${productId}/theme-reviews`,
      {
        params: { theme, sentiment, limit },
        timeout: DEFAULT_TIMEOUT_MS,
        signal,
      }
    );
    return response.data;
  } catch (error) {
    return handleApiError(error, 'Failed to fetch supporting reviews.');
  }
}

/**
 * Discovers similar products in the same dataset category.
 */
export async function getSimilarProducts(
  productId: string,
  limit: number = 3,
  signal?: AbortSignal
): Promise<ProductSummary[]> {
  try {
    const response = await apiClient.get<ProductSummary[]>(`/api/products/${productId}/similar`, {
      params: { limit },
      timeout: DEFAULT_TIMEOUT_MS,
      signal,
    });
    return response.data;
  } catch (error) {
    return handleApiError(error, 'Failed to fetch similar products.');
  }
}

/**
 * Generates personalized recommendation and side-by-side comparison based on user requirements.
 */
export async function getPersonalizedRecommendation(
  productId: string,
  requirements: UserRequirementRequest,
  signal?: AbortSignal
): Promise<PersonalizedRecommendationResponse> {
  try {
    const response = await apiClient.post<PersonalizedRecommendationResponse>(
      `/api/products/${productId}/recommendation`,
      requirements,
      {
        timeout: AI_ANALYSIS_TIMEOUT_MS,
        signal,
      }
    );
    return response.data;
  } catch (error) {
    return handleApiError(error, 'Failed to generate recommendation.');
  }
}

/**
 * Phase 5: retrieves the full real product intelligence payload.
 *
 * Returns the structured error body (never a partial payload) when the backend
 * reports one, so the caller can render an explicit error state.
 */
export async function getProductIntelligence(
  productId: string,
  signal?: AbortSignal
): Promise<ProductIntelligence | AnalysisErrorResponse> {
  try {
    const response = await apiClient.get<ProductIntelligence | AnalysisErrorResponse>(
      `/api/products/${productId}/intelligence`,
      { timeout: INTELLIGENCE_TIMEOUT_MS, signal }
    );
    return response.data;
  } catch (error) {
    return handleApiError(error, 'Failed to retrieve product intelligence.');
  }
}

/**
 * Retrieves paginated canonical dataset reviews for a product from the dataset.
 */
export async function getProductReviews(
  productId: string,
  params: {
    page?: number;
    limit?: number;
    rating?: number;
    sentiment?: string;
  },
  signal?: AbortSignal
): Promise<ReviewsPaginationResponse> {
  try {
    const response = await apiClient.get<ReviewsPaginationResponse>(
      `/api/products/${productId}/reviews`,
      {
        params,
        timeout: DEFAULT_TIMEOUT_MS,
        signal,
      }
    );
    return response.data;
  } catch (error) {
    return handleApiError(error, 'Failed to fetch product reviews.');
  }
}

/**
 * Generates an AI summary constrained strictly to retrieved dataset reviews for a product.
 */
export async function generateAISummary(
  productId: string,
  signal?: AbortSignal
): Promise<AISummaryResponse> {
  try {
    const response = await apiClient.post<AISummaryResponse>(
      `/api/products/${productId}/ai-summary`,
      {},
      { timeout: AI_ANALYSIS_TIMEOUT_MS, signal }
    );
    return response.data;
  } catch (error) {
    return handleApiError(error, 'Failed to generate summary.');
  }
}

/**
 * Retrieves overall dataset analytics calculated from the actual CSV.
 */
export async function getOverview(signal?: AbortSignal): Promise<OverviewAnalytics> {
  try {
    const response = await apiClient.get<OverviewAnalytics>('/api/analytics/overview', {
      timeout: DEFAULT_TIMEOUT_MS,
      signal,
    });
    return response.data;
  } catch (error) {
    return handleApiError(error, 'Failed to fetch overview analytics.');
  }
}

/**
 * Retrieves per-product / ASIN aggregated metrics.
 */
export async function getProducts(limit: number = 100, signal?: AbortSignal): Promise<ProductAnalytics[]> {
  try {
    const response = await apiClient.get<ProductAnalytics[]>('/api/analytics/products', {
      params: { limit },
      timeout: DEFAULT_TIMEOUT_MS,
      signal,
    });
    return response.data;
  } catch (error) {
    return handleApiError(error, 'Failed to fetch products analytics.');
  }
}

/**
 * Queries canonical dataset reviews from the dataset with search, filters, and pagination.
 */
export async function getDatasetReviews(
  params: {
    limit: number;
    offset: number;
    search?: string;
    rating?: number;
    sentiment?: string;
    product?: string;
  },
  signal?: AbortSignal
): Promise<DatasetReviewsResponse> {
  try {
    const response = await apiClient.get<DatasetReviewsResponse>('/api/dataset/reviews', {
      params,
      timeout: DEFAULT_TIMEOUT_MS,
      signal,
    });
    return response.data;
  } catch (error) {
    return handleApiError(error, 'Failed to fetch dataset reviews.');
  }
}

/**
 * Retrieves cached AI evaluation metrics comparing actual vs predicted ratings/sentiments.
 */
export async function getEvaluation(signal?: AbortSignal): Promise<EvaluationMetrics | null> {
  try {
    const response = await apiClient.get<EvaluationMetrics | null>('/api/evaluation', {
      timeout: DEFAULT_TIMEOUT_MS,
      signal,
    });
    return response.data;
  } catch {
    return null;
  }
}

/**
 * Triggers AI evaluation over a subset of canonical dataset reviews.
 */
export async function runEvaluation(
  limit: number = 10,
  reanalyze: boolean = false,
  signal?: AbortSignal
): Promise<EvaluationMetrics> {
  try {
    const response = await apiClient.post<EvaluationMetrics>(
      '/api/evaluation/run',
      {},
      {
        params: { limit, reanalyze },
        timeout: EVALUATION_TIMEOUT_MS,
        signal,
      }
    );
    return response.data;
  } catch (error) {
    return handleApiError(error, 'Evaluation run failed.');
  }
}

/**
 * Asks a free-text question about one product's stored reviews (Phase 7
 * `POST /api/products/{product_id}/rag-query`).
 *
 * The query is sent verbatim — never trimmed or rewritten — matching the
 * backend contract (whitespace-only input is rejected there with 422; the
 * FastAPI array-shaped validation detail is converted to a readable message
 * by `handleApiError`, which keeps plain-string details working too). An empty
 * `answer` in the response is a legitimate result (RAG disabled, empty
 * retrieval, or the answer discarded by citation/evidence validation);
 * callers must render exactly what the backend returned and never invent
 * content for it.
 */
export async function askProductQuestion(
  productId: string,
  query: string,
  signal?: AbortSignal
): Promise<RAGQueryResponse> {
  try {
    const response = await apiClient.post<RAGQueryResponse>(
      `/api/products/${productId}/rag-query`,
      { query },
      { timeout: AI_ANALYSIS_TIMEOUT_MS, signal }
    );
    return response.data;
  } catch (error) {
    return handleApiError(error, 'Failed to answer the question from reviews.');
  }
}
