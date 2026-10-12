// Phase 5 product intelligence contract.
// Mirrors backend/models/intelligence.py — every rendered value comes from the
// real API; nothing here has a default that could stand in for real data.

export interface DateRange {
  earliest: string | null;
  latest: string | null;
}

export interface EvidenceItem {
  review_id: string;
  excerpt: string;
}

export interface ClaimWithEvidence {
  claim: string;
  evidence: EvidenceItem[]; // backend enforces at least one
  support_count: number;
}

export interface AspectResult {
  aspect_name: string;
  sentiment: 'positive' | 'negative' | 'mixed';
  mention_count: number;
  representative_quote: EvidenceItem;
}

export interface ProductStatistics {
  total_reviews: number;
  average_rating: number;
  // JSON object keys are always strings; values are the counts per star.
  rating_distribution: Record<string, number>;
  sentiment_distribution: Record<string, number>;
  verified_purchase_pct: number;
  date_range: DateRange;
}

export interface ProductIntelligence {
  product_id: string;
  product_name: string;
  statistics: ProductStatistics;
  aspects: AspectResult[];
  pros: ClaimWithEvidence[];
  cons: ClaimWithEvidence[];
  summary: string;
  best_for: string;
  data_source: 'supabase';
  review_count_used: number;
  generated_at: string;
  low_review_count: boolean;
  ai_unavailable: boolean;
}

export type AnalysisErrorCode =
  | 'validation_error'
  | 'product_not_found'
  | 'insufficient_reviews'
  | 'ai_unavailable';

export interface AnalysisErrorResponse {
  code: AnalysisErrorCode;
  error: string;
  detail?: string | null;
}

export function isAnalysisError(
  value: ProductIntelligence | AnalysisErrorResponse
): value is AnalysisErrorResponse {
  return (value as AnalysisErrorResponse).code !== undefined;
}

/** Star keys 5→1 as strings, matching the JSON payload. */
export const STAR_KEYS_DESC = ['5', '4', '3', '2', '1'] as const;
