export interface ProductSummary {
  product_id: string;
  product_title: string;
  category?: string | null;
  review_count: number;
  average_rating: number;
}

export interface ProductSearchResponse {
  found: boolean;
  products: ProductSummary[];
  message?: string | null;
}

export interface ProductStatistics {
  review_count: number;
  average_rating: number;
  rating_distribution: Record<string, number>;
  sentiment_distribution: Record<string, number>;
}

export interface ReviewItem {
  id: number;
  product_id: string;
  product_title: string;
  category?: string | null;
  review_text: string;
  rating: number;
  sentiment: string;
}

export interface ProductAnalysisResponse {
  product: ProductSummary;
  statistics: ProductStatistics;
  recent_reviews: ReviewItem[];
}

export interface ReviewsPaginationResponse {
  items: ReviewItem[];
  total: number;
  page: number;
  limit: number;
  total_pages: number;
}

export interface AISummaryResponse {
  summary: string;
  common_pros: string[];
  common_cons: string[];
  key_themes: string[];
  source_label: string;
}

export interface ProConTheme {
  theme: string;
  review_count: number;
  percentage: number;
  example_reviews: string[];
  evidence_review_ids: number[];
}

export interface ProsConsAnalysisResponse {
  product_id: string;
  product_title: string;
  total_analyzed_reviews: number;
  pros: ProConTheme[];
  cons: ProConTheme[];
  summary: string;
  top_pros: string[];
  top_cons: string[];
  review_volume: number;
  average_rating: number;
  sentiment_percentages: Record<string, number>;
  authenticity_signals: string[];
  source_label: string;
}

export interface UserRequirementRequest {
  persona?: string;
  custom_requirements?: string;
  priorities?: string[];
  budget?: string;
}

export interface ProductComparisonItem {
  product_id: string;
  product_title: string;
  category: string;
  average_rating: number;
  review_count: number;
  positive_percentage: number;
  negative_percentage: number;
  neutral_percentage: number;
  common_pros: string[];
  common_cons: string[];
  is_selected: boolean;
}

export interface PriorityMatchEvidence {
  priority: string;
  evidence_level: string;
  details: string;
  supporting_reviews: string[];
}

export interface PersonalizedRecommendationResponse {
  selected_product: ProductSummary;
  recommended_product: ProductSummary;
  user_priorities: string[];
  priority_matches: PriorityMatchEvidence[];
  suitability_verdict: string;
  suitable_for: string[];
  consider_before_buying: string[];
  comparison_products: ProductComparisonItem[];
  recommendation_headline: string;
  recommendation_reasons: string[];
  strengths_for_you: string[];
  things_to_consider: string[];
  source_label: string;
}
