// Collections list-mode column geometry + sort metadata. Shared between
// CollectionListHeader (clickable column titles) and CollectionListRow
// (body rows) so the title row and every row underneath line up and
// surface the same sortable columns.
//
// Four columns: name (stretches) + kind (120px, standard/smart/virtual)
// + visibility (120px, public/private; display-only) + game count
// (96px, right-aligned).

export type CollectionListSortKey =
  | "name"
  | "kind"
  | "visibility"
  | "rom_count";

export interface CollectionListColumn {
  /** Unique column id. */
  key: CollectionListSortKey;
  /** i18n key for the header label — resolved in CollectionListHeader. */
  labelKey: string;
  /** Sort axis when the column is sortable; omitted for display-only columns. */
  sortKey?: CollectionListSortKey;
  align?: "start" | "end";
}

export const COLLECTION_LIST_COLUMNS: readonly CollectionListColumn[] = [
  { key: "name", labelKey: "common.name", sortKey: "name", align: "start" },
  { key: "kind", labelKey: "common.kind", sortKey: "kind", align: "start" },
  {
    key: "visibility",
    labelKey: "common.visibility",
    sortKey: "visibility",
    align: "start",
  },
  {
    key: "rom_count",
    labelKey: "common.games",
    sortKey: "rom_count",
    align: "end",
  },
];

export const COLLECTION_LIST_GRID_TEMPLATE = "minmax(0, 1fr) 120px 120px 96px";
