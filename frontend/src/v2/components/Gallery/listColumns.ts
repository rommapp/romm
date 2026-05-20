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
  | "fs_size_bytes"
  | "created_at"
  | "first_release_date"
  | "average_rating"
>;

export interface ListColumn {
  /** Sort key (matches `galleryRoms.orderBy`). `null` for non-sortable
   * display-only columns (icon labels, action menus). */
  key: ListSortKey | "select" | "languages" | "regions" | "actions";
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

export const LIST_COLUMNS: readonly ListColumn[] = [
  { key: "select", label: "", sortable: false, align: "start" },
  { key: "name", label: "Title", sortable: true, align: "start" },
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
];

/** Single grid template applied to both the header row and every body
 * row so columns line up vertically across the whole list. */
export const LIST_GRID_TEMPLATE =
  "36px minmax(0, 1.6fr) 88px 96px 84px 56px 110px 110px 56px";

// Numeric mirrors of the list-mode tokens so JS consumers (the
// virtualiser, the cover skeleton block) stay synced with the rendered
// CSS. Token values are guaranteed to be `<number>px` strings.
export const LIST_ROW_HEIGHT_PX = parseInt(layout.listRowHeight, 10);
export const LIST_HEADER_HEIGHT_PX = parseInt(layout.listHeaderHeight, 10);
export const LIST_COVER_WIDTH_PX = parseInt(layout.listCoverWidth, 10);
export const LIST_COVER_HEIGHT_PX = parseInt(layout.listCoverHeight, 10);
