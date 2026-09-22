export type SentimentType = 'positive' | 'negative' | 'neutral';

export interface ReviewAnalysis {
  sentiment: SentimentType;
  rating: number; // 1 to 5
  pros: string[];
  cons: string[];
  summary: string;
}

export interface AnalyzeReviewResponse {
  success: boolean;
  data?: ReviewAnalysis;
  error?: string;
}

export interface ReviewHistoryItem {
  id: string;
  reviewText: string;
  analysis: ReviewAnalysis;
  createdAt: string; // ISO string
}

export interface DashboardStats {
  totalReviews: number;
  positiveReviews: number;
  negativeReviews: number;
  neutralReviews: number;
  averageRating: number;
}
