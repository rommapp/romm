// Faceted filtering for the Platforms index: values inside one facet are
// OR-ed, facets are AND-ed, and each facet's option counts ignore that
// facet's own selection so picking "Console" still shows how many
// portables there are to add.

export const PLATFORM_FACET_KEYS = [
  "category",
  "generation",
  "family",
  "play",
] as const;
export type PlatformFacetKey = (typeof PLATFORM_FACET_KEYS)[number];

export type FacetSelection<K extends string> = Partial<
  Record<K, readonly string[]>
>;

export type FacetValuesOf<T, K extends string> = (
  item: T,
  key: K,
) => readonly string[];

export interface FacetOption {
  value: string;
  label: string;
  count: number;
}

export function filterByFacets<T, K extends string>(
  items: readonly T[],
  selection: NoInfer<FacetSelection<K>>,
  valuesOf: FacetValuesOf<T, K>,
  except?: NoInfer<K>,
): T[] {
  const active = (Object.entries(selection) as [K, readonly string[]][]).filter(
    ([key, picked]) => key !== except && picked.length > 0,
  );
  if (!active.length) return [...items];
  return items.filter((item) =>
    active.every(([key, picked]) =>
      valuesOf(item, key).some((v) => picked.includes(v)),
    ),
  );
}

/**
 * Options for one facet, counted against every other facet's selection.
 *
 * Args:
 *   universe: items the facet may describe (already search-filtered).
 *   labelOf: display label for a raw value.
 *   compare: option order; defaults to label order.
 */
export function facetOptions<T, K extends string>(
  universe: readonly T[],
  key: NoInfer<K>,
  selection: NoInfer<FacetSelection<K>>,
  valuesOf: FacetValuesOf<T, K>,
  labelOf: (value: string) => string,
  compare: (a: FacetOption, b: FacetOption) => number = (a, b) =>
    a.label.localeCompare(b.label),
): FacetOption[] {
  // Seed from the whole universe so an option narrowed to zero stays put
  // in the menu instead of vanishing under the cursor.
  const counts = new Map<string, number>();
  for (const item of universe) {
    for (const v of valuesOf(item, key)) counts.set(v, 0);
  }
  for (const v of selection[key] ?? []) counts.set(v, 0);
  for (const item of filterByFacets(universe, selection, valuesOf, key)) {
    for (const v of valuesOf(item, key)) {
      counts.set(v, (counts.get(v) ?? 0) + 1);
    }
  }
  return [...counts.entries()]
    .map(([value, count]) => ({ value, label: labelOf(value), count }))
    .sort(compare);
}

/** Comma-separated query value ⇄ list, dropping empties and duplicates. */
export function parseFacetParam(raw: string): string[] {
  return [...new Set(raw.split(",").filter(Boolean))];
}

export function formatFacetParam(values: readonly string[]): string {
  return [...new Set(values)].join(",");
}
