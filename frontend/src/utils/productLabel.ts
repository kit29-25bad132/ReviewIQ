// Phase 6C-C1: product display labels for the insights benchmark table.
//
// The API always sends both fields (backend/routes/analytics.py:
// asin = source_product_id, product_name = products.name). The UI must show
// the human-readable name first and the canonical ID second, and must never
// render the old literal "Product" placeholder.

import type { ProductAnalytics } from '../types/review';
import type { ProductSummary } from '../types/ecommerce';

export interface ProductLabelInput {
  asin?: string | null;
  product_name?: string | null;
}

export interface ProductLabel {
  /** Primary, human-readable label: product_name when usable, else asin. */
  name: string;
  /** Canonical product ID (source_product_id), or null when absent. */
  id: string | null;
}

function isBlank(value?: string | null): boolean {
  return value == null || value.trim() === '';
}

/**
 * Resolve the display label for one analytics row.
 *
 * Falls back to the product ID only when `product_name` is null, empty, or
 * whitespace-only. Returns an empty name only when both fields are unusable;
 * callers then render an em dash rather than a placeholder word.
 */
export function productLabel(product: ProductLabelInput): ProductLabel {
  const id = isBlank(product.asin) ? null : (product.asin as string);
  if (!isBlank(product.product_name)) {
    return { name: product.product_name as string, id };
  }
  return { name: id ?? '', id };
}

// Phase 6C-C2: the object handed to onSelectProduct when the insights table's
// Analyze button is clicked.
//
// - `product_title` comes from productLabel(): the real catalog name, falling
//   back to the ID only when the name is unusable — never the literal
//   "Product" and never the ID while a name exists.
// - `category` is deliberately OMITTED: the analytics endpoint does not
//   provide it, and the previous hardcoded "Dataset Product" fake is gone.
//   Consumers use the optional field's own fallback (Dashboard renders
//   "Product Selected" when category is absent).
// - `product_id` keeps the exact pre-C2 semantics (`p.asin || ''`).

export function insightsProductSummary(p: ProductAnalytics): ProductSummary {
  return {
    product_id: p.asin || '',
    product_title: productLabel(p).name,
    review_count: p.review_count,
    average_rating: p.average_actual_rating,
  };
}

// Phase 6C-C3: how many products the page can ever fetch in one call.
// Matches the backend ceiling (routes/analytics.py: limit le=500) — verified
// live: limit=501 -> 422, limit=500 -> full catalog. No offset exists (it is
// silently ignored), so this cap is the honest upper bound of the listing.

export const CATALOG_FETCH_CAP = 500;

/**
 * Display label for the fetched product count.
 *
 * Exact count below `cap`; `"${cap}+"` once the count reaches the cap, so the
 * UI never claims completeness it cannot prove at the API ceiling. Zero is
 * reported as `"0"`.
 */
export function catalogCountLabel(count: number, cap: number = CATALOG_FETCH_CAP): string {
  if (count >= cap) {
    return `${cap}+`;
  }
  return String(count);
}
