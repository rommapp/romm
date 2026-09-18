// List-mode column config shared between `GameListHeader` (sortable
// column titles), `GameListRow` (real + per-position skeleton bodies)
// and `GameListSkeletonRow` (bootstrap-phase placeholder rows).
//
// CSS grid template lives here so all three components pick up the same
// column geometry — change column widths in one place and the header
// stays aligned with every row underneath. The fr units in the title
// column let the row stretch to fill remaining width while the metric
// columns hold fixed pixel widths so numbers align cleanly.
//
// Pixel constants (`LIST_ROW_HEIGHT_PX`, `LIST_COVER_*_PX`, …) are
// derived from the design tokens so the JS-side virtualiser height table
// (`useGalleryVirtualItems`) stays in lock-step with the rendered CSS.
import i18n from "@/locales";
import type { GalleryOrderKey } from "@/v2/stores/galleryRoms";
import { layout } from "@/v2/tokens";

// Callers build the column set inside a `computed`, so reading the
// composer here keeps the labels reactive to a locale switch.
const t = (key: string) => i18n.global.t(key);

/** Subset of `GalleryOrderKey` exposed as clickable column headers in
 * list mode. Other gallery surfaces (toolbar dropdown, future smart
 * collections) may use additional keys from `GalleryOrderKey`. */
export type ListSortKey = Extract<
  GalleryOrderKey,
  | "name"
  | "platform_id"
  | "fs_size_bytes"
  | "created_at"
  | "first_release_date"
  | "average_rating"
  | "hltb_main_story"
>;

export interface ListColumn {
  /** Sort key (matches `galleryRoms.orderBy`). `null` for non-sortable
   * display-only columns (icon labels, action menus). */
  key: ListSortKey | "select" | "cover" | "languages" | "regions" | "actions";
  /** Column header label. Empty string renders no text (used for the
   * leading select column + trailing actions column). */
  label: string;
  /** Whether the column header is clickable to toggle sort. */
  sortable: boolean;
  /** Column alignment, read by the header label, the value cells and the
   *  actions cell; the structural cells lay themselves out. */
  align?: "start" | "end";
  /** Digit-bearing value, rendered in tabular figures so the column reads
   *  as a grid. */
  numeric?: boolean;
  /** Skeleton placeholder width (px) for this column's loading state.
   * `undefined` means the column owns a custom skeleton shape — the
   * title column paints cover + meta lines, the actions column paints
   * nothing. */
  skeletonWidth?: number;
}

/** Build the list-mode column set. Cross-platform surfaces (Search /
 * Collection / Missing games) include the `platform` column so each row
 * can show which platform it belongs to; single-platform surfaces
 * (Platform view) drop it since every row would carry the same value. */
export function getListColumns(showPlatform: boolean): readonly ListColumn[] {
  const cols: ListColumn[] = [
    { key: "select", label: "", sortable: false, align: "start" },
    // Cover gets its own fixed-width column so the title/meta column starts
    // at the same x on every row, regardless of the cover's natural width.
    { key: "cover", label: "", sortable: false, align: "start" },
    {
      key: "name",
      label: t("settings.title-header"),
      sortable: true,
      align: "start",
    },
  ];
  if (showPlatform) {
    cols.push({
      key: "platform_id",
      label: t("common.platform"),
      sortable: true,
      align: "start",
      skeletonWidth: 100,
    });
  }
  cols.push(
    {
      key: "fs_size_bytes",
      label: t("common.size"),
      sortable: true,
      align: "end",
      numeric: true,
      skeletonWidth: 60,
    },
    {
      key: "created_at",
      label: t("settings.added-header"),
      sortable: true,
      align: "end",
      numeric: true,
      skeletonWidth: 64,
    },
    {
      key: "first_release_date",
      label: t("settings.released-header"),
      sortable: true,
      align: "end",
      numeric: true,
      skeletonWidth: 40,
    },
    {
      key: "average_rating",
      label: t("settings.rating-header"),
      sortable: true,
      align: "end",
      numeric: true,
      skeletonWidth: 32,
    },
    {
      key: "hltb_main_story",
      label: t("settings.length-header"),
      sortable: true,
      align: "end",
      numeric: true,
      skeletonWidth: 40,
    },
    {
      key: "languages",
      label: t("rom.languages"),
      sortable: false,
      align: "start",
      skeletonWidth: 80,
    },
    {
      key: "regions",
      label: t("rom.regions"),
      sortable: false,
      align: "start",
      skeletonWidth: 80,
    },
    { key: "actions", label: "", sortable: false, align: "end" },
  );
  return cols;
}

// Fixed track widths (px) — kept as data so the grid template AND the row's
// natural min-width (below) derive from the same numbers.
const LIST_SELECT_TRACK_PX = 36;
const LIST_PLATFORM_TRACK_PX = 200;
const LIST_METRIC_TRACKS_PX = [88, 96, 96, 56, 72, 110, 110, 88];
/** Minimum width of the title column so it stays readable when the row is
 *  scrolled horizontally on a narrow viewport (instead of collapsing to 0). */
export const LIST_TITLE_MIN_PX = 200;

// Numeric mirrors of the list-mode tokens so JS consumers (the
// virtualiser, the cover skeleton block) stay synced with the rendered
// CSS. Token values are guaranteed to be `<number>px` strings.
//
// The list-row avatar is rendered by `<GameCard size="xs" />`, so the
// cover dimensions come from the shared xs tokens — there's no
// dedicated "list cover" token any more. Keep these JS mirrors so the
// skeleton placeholder paints at the same footprint as the real card.
export const LIST_ROW_HEIGHT_PX = parseInt(layout.listRowHeight, 10);
export const LIST_HEADER_HEIGHT_PX = parseInt(layout.listHeaderHeight, 10);
export const LIST_COVER_WIDTH_PX = parseInt(layout.cardArtWidthXs, 10);
export const LIST_COVER_HEIGHT_PX = parseInt(layout.cardArtHeightXs, 10);

/** Width (px) of the cover column: the widest footprint the row's cover can
 *  paint at. Fixed, not derived from measured ratios, which land later. */
export const LIST_COVER_TRACK_PX = LIST_COVER_HEIGHT_PX;

/** Placeholder bars for the title cell, shared by `GameListRow`'s own skeleton
 *  and the bootstrap-phase `GameListSkeletonRow` so the two can't drift. */
export const LIST_TITLE_SKELETON_BARS = [
  { width: "60%", height: 12 },
  { width: "40%", height: 10 },
] as const;
export const LIST_TITLE_SKELETON_GAP_PX = 2;

/** CSS-grid template paired with `getListColumns`. The `platform` slot
 * is inserted between `name` and `fs_size_bytes` when present so column
 * order matches the array. */
export function getListGridTemplate(showPlatform: boolean): string {
  const platformTrack = showPlatform ? ` ${LIST_PLATFORM_TRACK_PX}px` : "";
  const metrics = LIST_METRIC_TRACKS_PX.map((w) => `${w}px`).join(" ");
  // A fixed cover track keeps the title column at the same x in every row,
  // including the loading placeholders.
  return `${LIST_SELECT_TRACK_PX}px ${LIST_COVER_TRACK_PX}px minmax(${LIST_TITLE_MIN_PX}px, 1.6fr)${platformTrack} ${metrics}`;
}

// The row/header grids also carry a `--r-space-5` column gap and a
// `--r-space-3` inline padding on each side (see GameListRow / GameListHeader),
// which add to the natural width alongside the tracks.
const LIST_GRID_GAP_PX = 20; // --r-space-5
const LIST_ROW_PAD_X_PX = 12; // --r-space-3 (each side)

/** The row's natural (minimum) width = every fixed track + the title's floor +
 *  the inter-column gaps + the row's inline padding. The shell hands this to
 *  the virtual scroller as its `minContentWidth`, so a viewport narrower than
 *  this scrolls the list horizontally instead of squashing / clipping the
 *  columns (and it sizes the sticky column header to match). */
export function getListMinWidth(showPlatform: boolean): number {
  const metrics = LIST_METRIC_TRACKS_PX.reduce((a, b) => a + b, 0);
  // Columns: select + cover + title (+ platform) + every metric.
  const columnCount = 3 + LIST_METRIC_TRACKS_PX.length + (showPlatform ? 1 : 0);
  const tracks =
    LIST_SELECT_TRACK_PX +
    LIST_COVER_TRACK_PX +
    LIST_TITLE_MIN_PX +
    (showPlatform ? LIST_PLATFORM_TRACK_PX : 0) +
    metrics;
  return tracks + (columnCount - 1) * LIST_GRID_GAP_PX + 2 * LIST_ROW_PAD_X_PX;
}

/** Default exports — the cross-platform variant. Used by the bootstrap-
 * phase skeleton/header pair when no consumer-specific override is
 * available; per-view code should always go through the explicit
 * `getListColumns(...)` / `getListGridTemplate(...)` so the column set
 * reflects the active surface. */
export const LIST_COLUMNS = getListColumns(true);
export const LIST_GRID_TEMPLATE = getListGridTemplate(true);

/** `sortable` is what makes a column's key a sort key, so the flag is the
 *  narrowing test. */
export function isSortableColumn(
  column: ListColumn,
): column is ListColumn & { key: ListSortKey } {
  return column.sortable;
}

// The sort keys list mode can toggle, read off the columns themselves so a
// sortable column cannot go missing from them.
const LIST_SORT_KEYS: ReadonlySet<string> = new Set<string>(
  LIST_COLUMNS.filter(isSortableColumn).map((column) => column.key),
);

/** Whether the gallery's current order key is one list mode can sort by. */
export function isListSortKey(key: string): key is ListSortKey {
  return LIST_SORT_KEYS.has(key);
}
