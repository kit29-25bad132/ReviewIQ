import { describe, expect, it } from 'vitest';
import { insightsProductSummary } from './productLabel';
import type { ProductAnalytics } from '../types/review';

const row = (overrides: Partial<ProductAnalytics> = {}): ProductAnalytics => ({
  asin: 'P03',
  product_name: 'Orbix M14',
  review_count: 95,
  average_actual_rating: 3.14,
  positive_reviews: 40,
  neutral_reviews: 30,
  negative_reviews: 25,
  helpful_votes: 12,
  ...overrides,
});

describe('insightsProductSummary (6C-C2)', () => {
  it('uses the real catalog name as product_title', () => {
    const summary = insightsProductSummary(row());
    expect(summary.product_title).toBe('Orbix M14');
    expect(summary.product_id).toBe('P03');
  });

  it('falls back to the ID as title when product_name is missing', () => {
    expect(insightsProductSummary(row({ product_name: null })).product_title).toBe('P03');
    expect(insightsProductSummary(row({ product_name: '' })).product_title).toBe('P03');
    expect(insightsProductSummary(row({ product_name: '   ' })).product_title).toBe('P03');
  });

  it('omits category entirely instead of faking "Dataset Product"', () => {
    const summary = insightsProductSummary(row());
    expect('category' in summary).toBe(false);
    expect(JSON.stringify(summary)).not.toContain('Dataset Product');
  });

  it('never produces the literal "Product" placeholder', () => {
    expect(insightsProductSummary(row()).product_title).not.toBe('Product');
    expect(insightsProductSummary(row({ asin: 'P03', product_name: '' })).product_title).not.toBe(
      'Product'
    );
  });

  it('preserves product_id, review_count, and average_rating', () => {
    const summary = insightsProductSummary(row());
    expect(summary.product_id).toBe('P03');
    expect(summary.review_count).toBe(95);
    expect(summary.average_rating).toBe(3.14);
  });

  it('keeps pre-C2 product_id semantics (p.asin || empty string)', () => {
    expect(insightsProductSummary(row({ asin: null })).product_id).toBe('');
    expect(insightsProductSummary(row({ asin: undefined })).product_id).toBe('');
  });
});
