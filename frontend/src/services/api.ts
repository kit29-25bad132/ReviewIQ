import axios, { AxiosError } from 'axios';
import {
  ProductSearchResponse,
  ProductAnalysisResponse,
  ProsConsAnalysisResponse,
  AISummaryResponse,
  ReviewsPaginationResponse,
  ReviewItem,
} from '../types/ecommerce';
import {
  AnalyzeReviewResponse,
  ReviewAnalysis,
} from '../types/review';

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 60000, // 60s for AI pipeline
});

export interface HealthStatus {
  status: string;
  ai_configured: boolean;
  ai_provider: string;
}

/**
 * Checks backend health and AI engine status.
 */
export async function checkBackendHealth(): Promise<HealthStatus> {
  try {
    const response = await apiClient.get<HealthStatus>('/health', { timeout: 5000 });
    return response.data;
  } catch {
    return {
      status: 'offline',
      ai_configured: false,
      ai_provider: 'Unavailable',
    };
  }
}

/**
 * Helper to extract client-friendly error message from Axios errors.
 */
function extractErrorMessage(error: unknown, fallback: string): string {
  if (axios.isAxiosError(error)) {
    const axiosErr = error as AxiosError<{ detail?: string; error?: string; message?: string }>;
    if (axiosErr.response) {
      const data = axiosErr.response.data;
      if (data?.detail) return data.detail;
      if (data?.error) return data.error;
      if (data?.message) return data.message;
      if (axiosErr.response.status === 404) return 'The requested product or resource was not found.';
      if (axiosErr.response.status === 503) return 'ReviewIQ dataset engine is indexing or busy. Please retry shortly.';
      if (axiosErr.response.status === 422) return 'Invalid query parameters sent to the server.';
      if (axiosErr.response.status >= 500) return 'Internal server error while processing reviews.';
    } else if (axiosErr.code === 'ECONNABORTED') {
      return 'The intelligence analysis timed out. The server is processing large review volumes.';
    } else if (axiosErr.request) {
      return `Backend unavailable. Unable to reach ReviewIQ API service (${API_BASE_URL || 'local server'}).`;
    }
  }
  if (error instanceof Error) {
    return error.message;
  }
  return fallback;
}

/**
 * Searches products in the dataset with ranking.
 */
export async function searchProducts(q: string, limit: number = 20): Promise<ProductSearchResponse> {
  try {
    const response = await apiClient.get<ProductSearchResponse>('/api/products/search', {
      params: { q: q.trim() || undefined, limit },
    });
    return response.data;
  } catch (error) {
    throw new Error(extractErrorMessage(error, 'Failed to search products in the dataset.'));
  }
}

/**
 * Retrieves product statistics, rating & sentiment distribution, and recent reviews.
 */
export async function getProductAnalysis(productId: string): Promise<ProductAnalysisResponse> {
  try {
    const response = await apiClient.get<ProductAnalysisResponse>(`/api/products/${productId}/analysis`);
    return response.data;
  } catch (error) {
    throw new Error(extractErrorMessage(error, `Failed to retrieve analysis for product ${productId}.`));
  }
}

/**
 * Retrieves dynamic Pros & Cons with statistical review volume and percentages.
 */
export async function getProductProsCons(productId: string): Promise<ProsConsAnalysisResponse> {
  try {
    const response = await apiClient.get<ProsConsAnalysisResponse>(`/api/products/${productId}/pros-cons`);
    return response.data;
  } catch (error) {
    throw new Error(extractErrorMessage(error, `Failed to analyze pros and cons for product ${productId}.`));
  }
}

/**
 * Generates AI summary strictly grounded on retrieved customer reviews.
 */
export async function generateAISummary(productId: string): Promise<AISummaryResponse> {
  try {
    const response = await apiClient.post<AISummaryResponse>(
      `/api/products/${productId}/ai-summary`,
      {},
      { timeout: 60000 }
    );
    return response.data;
  } catch (error) {
    throw new Error(extractErrorMessage(error, `Failed to generate AI summary for product ${productId}.`));
  }
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
  try {
    const response = await apiClient.get<ReviewItem[]>(
      `/api/products/${productId}/theme-reviews`,
      {
        params: { theme, sentiment, limit },
      }
    );
    return response.data;
  } catch (error) {
    throw new Error(extractErrorMessage(error, `Failed to fetch supporting evidence reviews for "${theme}".`));
  }
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
  try {
    const response = await apiClient.get<ReviewsPaginationResponse>(
      `/api/products/${productId}/reviews`,
      { params }
    );
    return response.data;
  } catch (error) {
    throw new Error(extractErrorMessage(error, 'Failed to fetch customer reviews.'));
  }
}

/**
 * Analyzes an ad-hoc single review text using the LangGraph AI orchestrator.
 */
export async function analyzeReview(reviewText: string): Promise<ReviewAnalysis> {
  try {
    const response = await apiClient.post<AnalyzeReviewResponse>('/api/analyze-review', {
      review: reviewText,
    });

    if (response.data && response.data.success && response.data.data) {
      return response.data.data;
    }

    throw new Error(response.data?.error || 'Failed to analyze review text.');
  } catch (error) {
    throw new Error(extractErrorMessage(error, 'AI review analysis failed.'));
  }
}
