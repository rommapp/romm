// RTable column descriptor — drives both the header and the row body.
// Widths are CSS grid track values (px, fr, minmax(...)) so consumers
// can mix fixed-width metrics with flexible title columns the same way
// the gallery list does.
export interface RTableProps<TItem> {
  columns: readonly RTableColumn[];
  items: readonly TItem[];
  /** Stable key per row — either the property name (`"id"`) or a
   *  function returning a unique string/number. */
  itemKey: string | ((row: TItem) => string | number);
  /** Renders skeleton rows in place of `items`. Use during initial
   *  data load (the table chrome stays painted, no layout shift). */
  loading?: boolean;
  /** Number of skeleton rows to paint when `loading`. Default 6. */
  loadingRows?: number;
  /** Currently-sorted column key. `null` when no sort is active. */
  sortKey?: string | null;
  /** Sort direction for the active key. */
  sortDir?: RTableSortDir;
  /** Empty-state icon when `items` is empty and not loading. */
  emptyIcon?: string;
  /** Empty-state message. */
  emptyMessage?: string;
  /** Whether rows respond to hover / click. Click-binding is opt-in
   *  via the `row:click` listener — this just toggles the cursor. */
  clickableRows?: boolean;
  /** Per-row CSS row-height. Default uses `--r-list-row-h` token. */
  rowHeight?: string;
  /** Extra class merged into each row — useful for variant rows. */
  rowClass?: string | ((row: TItem) => string | undefined);
}

export interface RTableColumn {
  /** Unique column id — used as the cell-slot suffix (`cell.<key>`)
   *  and as the sort identifier emitted on header click. */
  key: string;
  /** Header label (leave empty for action / icon-only columns). */
  label: string;
  /** Header is clickable to toggle sort. */
  sortable?: boolean;
  /** Cell + header text alignment. Defaults to `start`. */
  align?: "start" | "end" | "center";
  /** CSS grid track width — `120px`, `minmax(0, 1.6fr)`, `1fr`, etc.
   *  Defaults to `minmax(0, 1fr)`. */
  width?: string;
  /** Skeleton placeholder bar width (px) for loading rows. */
  skeletonWidth?: number;
}

export type RTableSortDir = "asc" | "desc";

export interface RTableSortPayload {
  key: string;
  dir: RTableSortDir;
}
