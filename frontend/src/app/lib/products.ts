import type { Product } from "../types";

/** Minimum AI match score to surface explainability ("Why?") in the catalog. */
export const AI_RECOMMENDATION_THRESHOLD = 85;

export function isAiRecommended(product: Product): boolean {
  return product.aiScore >= AI_RECOMMENDATION_THRESHOLD;
}
