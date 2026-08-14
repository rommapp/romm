// Platforms list-mode column geometry. Shared between PlatformListHeader
// and PlatformListRow so the title row and every body row line up.
//
// Six columns: name (stretches) + family + category + generation +
// playable + game count (right-aligned). The three metadata columns +
// playable surface the same axes the toolbar can group by — so a user
// reading the list in a flat order can still see what would have
// separated them. The narrow-viewport template drops every metadata
// column to keep the row legible without horizontal scroll.

export type PlatformSortKey =
  "name" | "family" | "category" | "generation" | "playable" | "rom_count";

export interface PlatformColumn {
  key: PlatformSortKey;
  label: string;
  sortable: boolean;
  align?: "start" | "end" | "center";
  /** Drop this column on `xs` viewports (mirrors the row's compact
   * layout — see PlatformListRow / PlatformListHeader CSS). */
  meta?: boolean;
}

export const PLATFORM_COLUMNS: readonly PlatformColumn[] = [
  { key: "name", label: "Name", sortable: true, align: "start" },
  {
    key: "family",
    label: "Family",
    sortable: true,
    align: "start",
    meta: true,
  },
  {
    key: "category",
    label: "Category",
    sortable: true,
    align: "start",
    meta: true,
  },
  {
    key: "generation",
    label: "Generation",
    sortable: true,
    align: "start",
    meta: true,
  },
  {
    key: "playable",
    label: "Playable",
    sortable: true,
    align: "center",
    meta: true,
  },
  { key: "rom_count", label: "Games", sortable: true, align: "end" },
];

export const PLATFORM_LIST_GRID_TEMPLATE =
  "minmax(0, 1fr) 160px 130px 110px 88px 96px";

// Narrow-viewport template — drops every metadata column. Same name +
// games layout the list shipped with originally, so the mobile view
// stays the "pick a platform" affordance it always was.
export const PLATFORM_LIST_GRID_TEMPLATE_COMPACT = "minmax(0, 1fr) 96px";

// Label helpers shared by the row and the index view's group-by
// computeds, so the two surfaces never disagree on how a category or
// generation should be written.

/** Prettify an IGDB-style snake_case category ("portable_console" →
 *  "Portable console"). Empty string returns empty so the caller can
 *  decide on a placeholder. */
export function prettifyPlatformCategory(raw: string): string {
  return raw
    .split("_")
    .map((part) => (part ? part.charAt(0).toUpperCase() + part.slice(1) : part))
    .join(" ");
}

/** "1st generation" / "2nd generation" / … with English ordinals. */
export function platformGenerationLabel(n: number): string {
  const mod10 = n % 10;
  const mod100 = n % 100;
  let suffix: string;
  if (mod10 === 1 && mod100 !== 11) suffix = "st";
  else if (mod10 === 2 && mod100 !== 12) suffix = "nd";
  else if (mod10 === 3 && mod100 !== 13) suffix = "rd";
  else suffix = "th";
  return `${n}${suffix} generation`;
}
