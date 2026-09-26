export type SentimentType = 'positive' | 'negative' | 'neutral' | 'mixed';

export type RatingSource = 'explicit' | 'inferred' | 'not_found';

export interface PointEvidence {
  point: string;
  evidence: string;
}

// V2-P8: deterministic, application-computed evidence-support level.
// Never a model confidence score or probability.
export type AspectSupport = 'strong' | 'moderate' | 'weak';

export interface AspectSentiment {
  aspect: string;
  sentiment: SentimentType;
  evidence: string;
  support?: AspectSupport | null;
}

export interface ReviewAnalysis {
  sentiment: SentimentType;
  rating: number | null; // integer 1–5, or null when rating_source is not_found
  rating_source: RatingSource;
  summary: string;
  aspects: AspectSentiment[];
  pros: PointEvidence[];
  cons: PointEvidence[];
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

export interface DatasetReview {
  id: string;
  asin?: string | null;
  product_name?: string | null;
  review_text: string;
  actual_rating: number;
  summary?: string | null;
  review_date?: string | null;
  helpful_yes?: number | null;
  total_vote?: number | null;
  actual_sentiment: SentimentType;
}

export interface DatasetReviewsResponse {
  items: DatasetReview[];
  total: number;
  limit: number;
  offset: number;
}

export interface OverviewAnalytics {
  total_reviews: number;
  average_rating: number;
  positive_reviews: number;
  neutral_reviews: number;
  negative_reviews: number;
  rating_distribution?: Record<number, number>;
}

export interface ProductAnalytics {
  asin?: string | null;
  product_name?: string | null;
  review_count: number;
  average_actual_rating: number;
  average_ai_rating?: number | null;
  positive_reviews: number;
  neutral_reviews: number;
  negative_reviews: number;
  helpful_votes: number;
}

export interface EvaluationMetrics {
  evaluated_reviews: number;
  rating_accuracy: number;
  rating_mae: number;
  sentiment_accuracy: number;
  confusion_matrix: number[][];
  methodology: string;
}
