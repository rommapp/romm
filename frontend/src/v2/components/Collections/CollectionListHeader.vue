<script setup lang="ts">
// CollectionListHeader: column-header strip for the Collections
// list-mode view. Mirrors GameListHeader's anatomy: each sortable
// column is a button that toggles asc → desc → asc on the parent's
// sort state via the `sort` event.
import { RSortHeader, type RSortDir } from "@v2/lib";
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import ListSortMenu from "@/v2/components/shared/ListSortMenu.vue";
import { useBreakpoint } from "@/v2/composables/useBreakpoint";
import {
  COLLECTION_LIST_COLUMNS,
  COLLECTION_LIST_GRID_TEMPLATE,
  type CollectionListSortKey,
} from "./collectionListColumns";

interface Props {
  /** Currently-sorted column key. */
  sortKey: CollectionListSortKey;
  /** Sort direction for the active key. */
  sortDir: RSortDir;
}

defineProps<Props>();

const emit = defineEmits<{
  (e: "sort", payload: { key: CollectionListSortKey; dir: RSortDir }): void;
}>();

const { t } = useI18n();
const gridStyle = { gridTemplateColumns: COLLECTION_LIST_GRID_TEMPLATE };

// Phones and tablets drop the columns (the rows go compact), so the sort
// key they carried moves into a menu, same as the gallery's list header.
const { smAndDown } = useBreakpoint();
const sortOptions = computed(() =>
  COLLECTION_LIST_COLUMNS.flatMap((col) =>
    col.sortKey ? [{ key: col.sortKey, label: t(col.labelKey) }] : [],
  ),
);
</script>

<template>
  <div v-if="smAndDown" class="coll-list-header coll-list-header--compact">
    <ListSortMenu
      :options="sortOptions"
      :sort-key="sortKey"
      :sort-dir="sortDir"
      @sort="emit('sort', $event)"
    />
  </div>

  <div v-else class="coll-list-header" :style="gridStyle" role="row">
    <RSortHeader
      v-for="col in COLLECTION_LIST_COLUMNS"
      :key="col.key"
      :label="t(col.labelKey)"
      :sortable="!!col.sortKey"
      :active="!!col.sortKey && sortKey === col.sortKey"
      :dir="sortDir"
      :align="col.align"
      @sort="col.sortKey && emit('sort', { key: col.sortKey, dir: $event })"
    />
  </div>
</template>

<style scoped>
.coll-list-header {
  display: grid;
  align-items: center;
  gap: 0 var(--r-space-3);
  padding: 0 max(var(--r-space-3), var(--r-list-bleed, 0px));
  height: var(--r-list-header-h);
  /* Overridable so a pinned header can run it edge to edge (r-pinned-list-header). */
  border-bottom: var(--r-list-header-border, 1px solid var(--r-color-border));
}

/* Compact (phones / tablets): one sort control instead of the columns. */
.coll-list-header--compact {
  display: flex;
  align-items: center;
  padding: 0 var(--r-row-pad);
}
</style>
