import axios, { AxiosError } from 'axios';
import { AnalyzeReviewResponse, ReviewAnalysis } from '../types/review';

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30000, // 30s timeout for AI generation
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
