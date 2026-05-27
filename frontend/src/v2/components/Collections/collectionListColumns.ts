// Collections list-mode column geometry + sort metadata. Shared between
// CollectionListHeader (clickable column titles) and CollectionListRow
// (body rows) so the title row and every row underneath line up and
// surface the same sortable columns.
//
// Three columns: name (stretches) + kind (84px, regular/virtual/smart)
// + game count (96px, right-aligned).

export type CollectionListSortKey = "name" | "kind" | "rom_count";

export interface CollectionListColumn {
  key: CollectionListSortKey;
  /** i18n key for the header label — resolved in CollectionListHeader. */
  labelKey: string;
  sortable: boolean;
  align?: "start" | "end";
}

export const COLLECTION_LIST_COLUMNS: readonly CollectionListColumn[] = [
  { key: "name", labelKey: "common.name", sortable: true, align: "start" },
  { key: "kind", labelKey: "common.kind", sortable: true, align: "start" },
  {
    key: "rom_count",
    labelKey: "common.games",
    sortable: true,
    align: "end",
  },
];

export const COLLECTION_LIST_GRID_TEMPLATE = "minmax(0, 1fr) 84px 96px";
