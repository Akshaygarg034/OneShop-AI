import type { Product } from "../types";

/** Whether we have a real, backend-computed signal breakdown to explain for
 * this product. Every /catalog response includes one now (recommend.rank_products
 * scores the whole catalog, not just chat's top picks), so this is just a
 * presence check - NOT an arbitrary "is this score high enough" cutoff. An
 * older version gated this on aiScore >= 85, a threshold tuned against an
 * inflated client-side heuristic; once the score became a real, calibrated
 * confidence (usually well under 85), that cutoff silently hid the "Why?"
 * button on almost everything. Explainability shouldn't be rationed by a
 * magic number - if we scored it, we can explain it. */
export function isAiRecommended(product: Product): boolean {
  return Boolean(product.signals);
}
