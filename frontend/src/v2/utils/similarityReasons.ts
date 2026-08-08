import type { SimilarityReasonSchema } from "@/__generated__";

/**
 * Maps a recommendation reason onto an icon and a display label.
 *
 * Facets whose value is already a proper noun (a franchise, a company)
 * display that value directly, since "Metroid" explains the match better
 * than "Same franchise" does. Facets with no meaningful value of their own
 * fall back to a translated phrase.
 */

const FACET_ICONS: Record<string, string> = {
  collection: "mdi-bookmark-multiple-outline",
  franchise: "mdi-star-outline",
  company: "mdi-domain",
  genre: "mdi-shape-outline",
  game_mode: "mdi-account-group-outline",
  decade: "mdi-calendar-outline",
  igdb: "mdi-link-variant",
  top_rated: "mdi-trophy-outline",
};

const DEFAULT_ICON = "mdi-tag-outline";

/** Facets rendered as a translated phrase rather than their raw value. */
const TRANSLATED_FACETS: Record<string, string> = {
  igdb: "recommendations.reason-igdb",
  top_rated: "recommendations.reason-top-rated",
};

export function reasonIcon(reason: SimilarityReasonSchema): string {
  return FACET_ICONS[reason.facet] ?? DEFAULT_ICON;
}

export function reasonLabel(
  reason: SimilarityReasonSchema,
  t: (key: string) => string,
): string {
  const translationKey = TRANSLATED_FACETS[reason.facet];
  if (translationKey) {
    return t(translationKey);
  }

  // Decades arrive as the starting year ("1990") and read better with the
  // plural suffix the rest of the UI uses.
  if (reason.facet === "decade") {
    return `${reason.value}s`;
  }

  return reason.value;
}

/** The single most explanatory reason, used where only one chip fits. */
export function primaryReason(
  reasons: SimilarityReasonSchema[],
): SimilarityReasonSchema | null {
  return reasons[0] ?? null;
}
