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
} from '../types/ecommerce';

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 60000, // 60s timeout for AI generation
});

export interface HealthStatus {
  status: string;
  ai_configured: boolean;
  ai_provider: string;
}

/**
 * Sends customer review to backend for AI analysis.
 */
export async function analyzeReview(reviewText: string): Promise<ReviewAnalysis> {
  try {
    const response = await apiClient.post<AnalyzeReviewResponse>('/api/analyze-review', {
      review: reviewText,
    });

    if (response.data && response.data.success && response.data.data) {
      return response.data.data;
    }

    throw new Error(response.data?.error || 'Failed to analyze review');
  } catch (error) {
    if (axios.isAxiosError(error)) {
      const axiosErr = error as AxiosError<{ detail?: string; error?: string }>;

      if (axiosErr.response) {
        const detail = axiosErr.response.data?.detail || axiosErr.response.data?.error;
        if (detail) {
          throw new Error(detail);
        }
        if (axiosErr.response.status === 400) {
          throw new Error('Invalid review input. Please check the review text.');
        }
        if (axiosErr.response.status === 500) {
          throw new Error('AI analysis service encountered an error. Please try again.');
        }
      } else if (axiosErr.code === 'ECONNABORTED') {
        throw new Error('Request timed out. The AI model is taking longer than expected.');
      } else if (axiosErr.request) {
        throw new Error(`Backend Offline: Cannot connect to FastAPI backend at ${API_BASE_URL}.`);
      }
    }

    throw new Error(error instanceof Error ? error.message : 'An unknown error occurred while analyzing the review.');
  }
}

/**
 * Checks backend health and API configuration status.
 */
export async function checkBackendHealth(): Promise<HealthStatus> {
  try {
    const response = await apiClient.get<HealthStatus>('/health', { timeout: 4000 });
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
 * Searches products in the 4M-row dataset.
 */
export async function searchProducts(q: string, limit: number = 20): Promise<ProductSearchResponse> {
  const response = await apiClient.get<ProductSearchResponse>('/api/products/search', {
    params: { q: q.trim() || undefined, limit },
  });
  return response.data;
}

/**
 * Retrieves complete real dataset statistics for a product.
 */
export async function getProductAnalysis(productId: string): Promise<ProductAnalysisResponse> {
  const response = await apiClient.get<ProductAnalysisResponse>(`/api/products/${productId}/analysis`);
  return response.data;
}

/**
 * Retrieves dynamic Pros & Cons with statistical review counts and percentages.
 */
export async function getProductProsCons(productId: string): Promise<ProsConsAnalysisResponse> {
  const response = await apiClient.get<ProsConsAnalysisResponse>(`/api/products/${productId}/pros-cons`);
  return response.data;
}

/**
 * Retrieves actual supporting reviews for a specific Pro/Con theme from the dataset.
 */
export async function getThemeSupportingReviews(
  productId: string,
  theme: string,
  sentiment?: string,
  limit: number = 50
): Promise<ReviewItem[]> {
  const response = await apiClient.get<ReviewItem[]>(
    `/api/products/${productId}/theme-reviews`,
    {
      params: { theme, sentiment, limit },
    }
  );
  return response.data;
}

/**
 * Discovers similar products in the same dataset category.
 */
export async function getSimilarProducts(productId: string, limit: number = 3): Promise<ProductSummary[]> {
  const response = await apiClient.get<ProductSummary[]>(`/api/products/${productId}/similar`, {
    params: { limit },
  });
  return response.data;
}

/**
 * Generates personalized recommendation and side-by-side comparison based on user requirements.
 */
export async function getPersonalizedRecommendation(
  productId: string,
  requirements: UserRequirementRequest
): Promise<PersonalizedRecommendationResponse> {
  const response = await apiClient.post<PersonalizedRecommendationResponse>(
    `/api/products/${productId}/recommendation`,
    requirements
  );
  return response.data;
}

/**
 * Retrieves paginated actual customer reviews for a product from the dataset.
 */
export async function getProductReviews(
  productId: string,
  params: {
    page?: number;
    limit?: number;
    rating?: number;
    sentiment?: string;
  }
): Promise<ReviewsPaginationResponse> {
  const response = await apiClient.get<ReviewsPaginationResponse>(
    `/api/products/${productId}/reviews`,
    { params }
  );
  return response.data;
}

/**
 * Generates an AI summary constrained strictly to retrieved dataset reviews for a product.
 */
export async function generateAISummary(productId: string): Promise<AISummaryResponse> {
  const response = await apiClient.post<AISummaryResponse>(
    `/api/products/${productId}/ai-summary`,
    {},
    { timeout: 60000 }
  );
  return response.data;
}

/**
 * Retrieves overall dataset analytics calculated from the actual CSV.
 */
export async function getOverview(): Promise<OverviewAnalytics> {
  const response = await apiClient.get<OverviewAnalytics>('/api/analytics/overview');
  return response.data;
}

/**
 * Retrieves per-product / ASIN aggregated metrics.
 */
export async function getProducts(limit: number = 100): Promise<ProductAnalytics[]> {
  const response = await apiClient.get<ProductAnalytics[]>('/api/analytics/products', {
    params: { limit },
  });
  return response.data;
}

/**
 * Queries real reviews from the dataset with search, filters, and pagination.
 */
export async function getDatasetReviews(params: {
  limit: number;
  offset: number;
  search?: string;
  rating?: number;
  sentiment?: string;
  product?: string;
}): Promise<DatasetReviewsResponse> {
  const response = await apiClient.get<DatasetReviewsResponse>('/api/dataset/reviews', { params });
  return response.data;
}

/**
 * Retrieves cached AI evaluation metrics comparing actual vs predicted ratings/sentiments.
 */
export async function getEvaluation(): Promise<EvaluationMetrics | null> {
  const response = await apiClient.get<EvaluationMetrics | null>('/api/evaluation');
  return response.data;
}

/**
 * Triggers AI evaluation over a subset of real Kaggle dataset reviews.
 */
export async function runEvaluation(
  limit: number = 10,
  reanalyze: boolean = false
): Promise<EvaluationMetrics> {
  const response = await apiClient.post<EvaluationMetrics>(
    '/api/evaluation/run',
    {},
    {
      params: { limit, reanalyze },
      timeout: 180000, // 3 minutes for batch evaluation
    }
  );
  return response.data;
}
