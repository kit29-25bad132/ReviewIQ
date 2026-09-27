export type SentimentType = 'positive' | 'negative' | 'neutral' | 'mixed';

export type RatingSource = 'explicit' | 'inferred' | 'not_found';

export interface PointEvidence {
  point: string;
  evidence: string;
}

export interface AspectSentiment {
  aspect: string;
  sentiment: SentimentType;
  evidence: string;
}

export interface ReviewAnalysis {
  sentiment: SentimentType;
  rating: number | null;
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

export interface ProductIntelligenceData {
  product: import('./ecommerce').ProductSummary;
  statistics: import('./ecommerce').ProductStatistics;
  prosCons: import('./ecommerce').ProsConsAnalysisResponse | null;
  aiSummary: import('./ecommerce').AISummaryResponse | null;
  recentReviews: import('./ecommerce').ReviewItem[];
}
