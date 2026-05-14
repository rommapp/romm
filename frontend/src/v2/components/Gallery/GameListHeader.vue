<script setup lang="ts">
// GameListHeader — sticky column-header row for list-mode galleries.
//
// Layout: a single CSS-grid div sharing `LIST_GRID_TEMPLATE` with every
// `GameListRow` underneath, so columns line up regardless of viewport.
// Click on a sortable column toggles asc → desc → asc (single-key sort,
// matching the rest of the gallery surface).
//
// Sticky positioning is owned by the parent (`GalleryShell` pins this
// below the toolbar at `top: --r-v2-shell-toolbar-h`). The header
// itself only paints — it doesn't manage scroll.
import { RIcon } from "@v2/lib";
import { computed } from "vue";
import {
  LIST_COLUMNS,
  LIST_GRID_TEMPLATE,
  type ListColumn,
  type ListSortKey,
} from "./listColumns";

interface Props {
  /** Currently-sorted column key. `null` when no sort is active. */
  sortKey: ListSortKey | null;
  /** Sort direction for the active key. */
  sortDir: "asc" | "desc";
}

const props = defineProps<Props>();

const emit = defineEmits<{
  (e: "sort", payload: { key: ListSortKey; dir: "asc" | "desc" }): void;
}>();

const gridStyle = computed(() => ({ gridTemplateColumns: LIST_GRID_TEMPLATE }));

function isSortable(col: ListColumn): col is ListColumn & { key: ListSortKey } {
  return col.sortable;
}

function handleClick(col: ListColumn) {
  if (!isSortable(col)) return;
  // Toggle direction when re-clicking the active column; otherwise
  // start the new column at ascending — consistent behaviour with
  // every other sortable table in the app.
  const nextDir: "asc" | "desc" =
    props.sortKey === col.key && props.sortDir === "asc" ? "desc" : "asc";
  emit("sort", { key: col.key, dir: nextDir });
}
</script>

<template>
  <div class="game-list-header" :style="gridStyle" role="row">
    <button
      v-for="col in LIST_COLUMNS"
      :key="String(col.key)"
      type="button"
      class="game-list-header__cell"
      :class="{
        'game-list-header__cell--sortable': col.sortable,
        'game-list-header__cell--end': col.align === 'end',
        'game-list-header__cell--active': col.sortable && sortKey === col.key,
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
      <span class="game-list-header__label">{{ col.label }}</span>
      <RIcon
        v-if="col.sortable && sortKey === col.key"
        :icon="sortDir === 'asc' ? 'mdi-arrow-up-thin' : 'mdi-arrow-down-thin'"
        size="14"
        class="game-list-header__icon"
      />
    </button>
  </div>
</template>

<style scoped>
.game-list-header {
  display: grid;
  align-items: center;
  gap: 0 var(--r-space-3);
  padding: 0 var(--r-space-3);
  height: var(--r-list-header-h);
  background: var(--r-color-bg-elevated);
  border-bottom: 1px solid var(--r-color-border);
  /* Glass tint so the BackgroundArt blur reads behind the row when the
     scroller's clip-path lifts at the toolbar/header band. */
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
}

.game-list-header__cell {
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

.game-list-header__cell--end {
  justify-content: flex-end;
  text-align: end;
}

.game-list-header__cell--sortable {
  cursor: pointer;
}

.game-list-header__cell--sortable:hover,
.game-list-header__cell--sortable:focus-visible {
  color: var(--r-color-fg);
}

.game-list-header__cell--active {
  color: var(--r-color-fg);
}

.game-list-header__label {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.game-list-header__icon {
  flex-shrink: 0;
  color: var(--r-color-brand-primary);
}
</style>
