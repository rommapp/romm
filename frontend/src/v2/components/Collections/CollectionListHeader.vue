<script setup lang="ts">
// CollectionListHeader — column-header strip for the Collections
// list-mode view. Mirrors GameListHeader's anatomy: each sortable
// column is a button that toggles asc → desc → asc on the parent's
// sort state via the `sort` event.
import { RIcon } from "@v2/lib";
import { useI18n } from "vue-i18n";
import {
  COLLECTION_LIST_COLUMNS,
  COLLECTION_LIST_GRID_TEMPLATE,
  type CollectionListColumn,
  type CollectionListSortKey,
} from "./collectionListColumns";

interface Props {
  /** Currently-sorted column key. */
  sortKey: CollectionListSortKey;
  /** Sort direction for the active key. */
  sortDir: "asc" | "desc";
}

const props = defineProps<Props>();

const emit = defineEmits<{
  (
    e: "sort",
    payload: { key: CollectionListSortKey; dir: "asc" | "desc" },
  ): void;
}>();

const { t } = useI18n();
const gridStyle = { gridTemplateColumns: COLLECTION_LIST_GRID_TEMPLATE };

function handleClick(col: CollectionListColumn) {
  if (!col.sortable) return;
  // Toggle direction when re-clicking the active column; otherwise
  // start the new column at ascending — same rule as GameListHeader.
  const nextDir: "asc" | "desc" =
    props.sortKey === col.key && props.sortDir === "asc" ? "desc" : "asc";
  emit("sort", { key: col.key, dir: nextDir });
}
</script>

<template>
  <div class="coll-list-header" :style="gridStyle" role="row">
    <button
      v-for="col in COLLECTION_LIST_COLUMNS"
      :key="col.key"
      type="button"
      class="coll-list-header__cell"
      :class="{
        'coll-list-header__cell--sortable': col.sortable,
        'coll-list-header__cell--end': col.align === 'end',
        'coll-list-header__cell--active': col.sortable && sortKey === col.key,
      }"
      :aria-sort="
        col.sortable && sortKey === col.key
          ? sortDir === 'asc'
            ? 'ascending'
            : 'descending'
          : 'none'
      "
      :tabindex="col.sortable ? 0 : -1"
      :disabled="!col.sortable"
      @click="handleClick(col)"
    >
      <span class="coll-list-header__label">{{ t(col.labelKey) }}</span>
      <RIcon
        v-if="col.sortable && sortKey === col.key"
        :icon="sortDir === 'asc' ? 'mdi-arrow-up-thin' : 'mdi-arrow-down-thin'"
        size="14"
        class="coll-list-header__icon"
      />
    </button>
  </div>
</template>

<style scoped>
.coll-list-header {
  display: grid;
  align-items: center;
  gap: 0 var(--r-space-3);
  padding: 0 var(--r-space-3);
  height: var(--r-list-header-h);
  background: var(--r-color-bg-elevated);
  border-bottom: 1px solid var(--r-color-border);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
}

.coll-list-header__cell {
  appearance: none;
  background: transparent;
  border: 0;
  padding: 0;
  font: inherit;
  color: var(--r-color-fg-secondary);
  font-size: var(--r-font-size-xs);
  font-weight: var(--r-font-weight-bold);
  letter-spacing: 0.07em;
  text-transform: uppercase;
  display: inline-flex;
  align-items: center;
  gap: var(--r-space-1);
  min-width: 0;
  height: 100%;
  cursor: default;
  text-align: start;
  border-radius: var(--r-radius-sm);
  transition: color var(--r-motion-fast) var(--r-motion-ease-out);
}

.coll-list-header__cell--end {
  justify-content: flex-end;
  text-align: end;
}

.coll-list-header__cell--sortable {
  cursor: pointer;
}

.coll-list-header__cell--sortable:hover,
.coll-list-header__cell--sortable:focus-visible {
  color: var(--r-color-fg);
}

.coll-list-header__cell--active {
  color: var(--r-color-fg);
}

.coll-list-header__label {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.coll-list-header__icon {
  flex-shrink: 0;
  color: var(--r-color-brand-primary);
}
</style>
