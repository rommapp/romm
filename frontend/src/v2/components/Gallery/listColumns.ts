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
import type { GalleryOrderKey } from "@/v2/stores/galleryRoms";
import { layout } from "@/v2/tokens";

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
  align?: "start" | "end";
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
    { key: "name", label: "Title", sortable: true, align: "start" },
  ];
  if (showPlatform) {
    cols.push({
      key: "platform_id",
      label: "Platform",
      sortable: true,
      align: "start",
      skeletonWidth: 100,
    });
  }
  cols.push(
    {
      key: "fs_size_bytes",
      label: "Size",
      sortable: true,
      align: "start",
      skeletonWidth: 60,
    },
    {
      key: "created_at",
      label: "Added",
      sortable: true,
      align: "start",
      skeletonWidth: 64,
    },
    {
      key: "first_release_date",
      label: "Released",
      sortable: true,
      align: "start",
      skeletonWidth: 40,
    },
    {
      key: "average_rating",
      label: "Rating",
      sortable: true,
      align: "start",
      skeletonWidth: 32,
    },
    {
      key: "languages",
      label: "Languages",
      sortable: false,
      align: "start",
      skeletonWidth: 80,
    },
    {
      key: "regions",
      label: "Regions",
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
const LIST_METRIC_TRACKS_PX = [88, 96, 84, 56, 110, 110, 88];
/** Minimum width of the title column so it stays readable when the row is
 *  scrolled horizontally on a narrow viewport (instead of collapsing to 0). */
export const LIST_TITLE_MIN_PX = 200;

/** CSS-grid template paired with `getListColumns`. The `platform` slot
 * is inserted between `name` and `fs_size_bytes` when present so column
 * order matches the array. */
export function getListGridTemplate(
  showPlatform: boolean,
  coverWidthPx = 48,
): string {
  const platformTrack = showPlatform ? ` ${LIST_PLATFORM_TRACK_PX}px` : "";
  const metrics = LIST_METRIC_TRACKS_PX.map((w) => `${w}px`).join(" ");
  // Cover track widens to the widest cover in the gallery (set by the
  // shell from measured ratios), so landscape covers show whole instead of
  // being clipped, while portrait-only lists stay tight. The title column
  // starts at a fixed x because every row shares this width.
  return `${LIST_SELECT_TRACK_PX}px ${coverWidthPx}px minmax(${LIST_TITLE_MIN_PX}px, 1.6fr)${platformTrack} ${metrics}`;
}

// The row/header grids also carry a `--r-space-3` column gap and a
// `--r-space-3` inline padding on each side (see GameListRow / GameListHeader),
// which add to the natural width alongside the tracks.
const LIST_GRID_GAP_PX = 12; // --r-space-3
const LIST_ROW_PAD_X_PX = 12; // --r-space-3 (each side)

/** The row's natural (minimum) width = every fixed track + the title's floor +
 *  the inter-column gaps + the row's inline padding. The shell hands this to
 *  the virtual scroller as its `minContentWidth`, so a viewport narrower than
 *  this scrolls the list horizontally instead of squashing / clipping the
 *  columns (and it sizes the sticky column header to match). */
export function getListMinWidth(
  showPlatform: boolean,
  coverWidthPx = 48,
): number {
  const metrics = LIST_METRIC_TRACKS_PX.reduce((a, b) => a + b, 0);
  // Columns: select + cover + title (+ platform) + every metric.
  const columnCount = 3 + LIST_METRIC_TRACKS_PX.length + (showPlatform ? 1 : 0);
  const tracks =
    LIST_SELECT_TRACK_PX +
    coverWidthPx +
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
