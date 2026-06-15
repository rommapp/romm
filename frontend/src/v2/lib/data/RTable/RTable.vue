<script setup lang="ts" generic="T">
// RTable — generic CSS-grid sortable table primitive.
//
// Visual + interaction language extracted from the gallery list view
// (`GameListHeader` / `GameListRow`) so every "table" surface in the
// app reads as a sibling: glass container, hairline-divided rows,
// sortable headers with a sliding direction icon, hover tint, skeleton
// rows during load, and an empty state when there's nothing to show.
//
// Generic `<T>` so consumers get full type-safety on the cell-slot
// payload (`{ row: T }`).
//
// Usage:
//   <RTable
//     :columns="cols"
//     :items="rows"
//     :item-key="(r) => r.id"
//     :sort-key="sortKey"
//     :sort-dir="sortDir"
//     @update:sort="onSort"
//   >
//     <template #cell.platform="{ row }">…</template>
//     <template #cell.actions="{ row }">…</template>
//   </RTable>
//
// Sort emits the new (key, dir) — toggling direction on the active
// column or starting at "asc" on a new column. The store/composable
// owns the actual sort state; RTable is pure UI.
import { computed } from "vue";
import RIcon from "../../primitives/RIcon/RIcon.vue";
import RSkeletonBlock from "../../primitives/RSkeletonBlock/RSkeletonBlock.vue";
import type {
  RTableColumn,
  RTableProps,
  RTableSortDir,
  RTableSortPayload,
} from "./types";

defineOptions({ inheritAttrs: false });

const props = withDefaults(defineProps<RTableProps<T>>(), {
  loading: false,
  loadingRows: 6,
  sortKey: null,
  sortDir: "asc",
  emptyIcon: "mdi-inbox-outline",
  emptyMessage: undefined,
  clickableRows: false,
  rowHeight: undefined,
  rowClass: undefined,
  minWidth: undefined,
});

const emit = defineEmits<{
  (e: "update:sort", payload: RTableSortPayload): void;
  (e: "row:click", row: T): void;
}>();

const gridTemplate = computed(() =>
  props.columns.map((c) => c.width ?? "minmax(0, 1fr)").join(" "),
);

const gridStyle = computed(() => ({ gridTemplateColumns: gridTemplate.value }));

// Optional horizontal-scroll floor. Without it columns shrink + ellipsis
// to fit (current behaviour). With it, header + body keep this min-width
// and the table scrolls horizontally below it — useful for many-column
// tables on narrow / mobile viewports. Set e.g. `min-width="640px"`.
const resolvedMinWidth = computed<string | undefined>(() => {
  const w = props.minWidth;
  if (w === undefined || w === null || w === "") return undefined;
  return typeof w === "number" ? `${w}px` : w;
});
const scrollStyle = computed(() =>
  resolvedMinWidth.value
    ? { "--r-table-min-w": resolvedMinWidth.value }
    : undefined,
);

function rowKey(row: T, idx: number): string | number {
  const key = props.itemKey;
  if (typeof key === "function") return key(row);
  const v = (row as Record<string, unknown>)[key];
  return (v as string | number | undefined) ?? idx;
}

function rowClassFor(row: T): string | undefined {
  const c = props.rowClass;
  return typeof c === "function" ? c(row) : c;
}

// Default cell renderer. Kept in the script (rather than inline in the
// template) so the generic cast doesn't put `<...>` angle brackets inside
// a mustache, which the HTML/Prettier parser misreads as tags.
function cellValue(row: T, key: string): unknown {
  return (row as Record<string, unknown>)[key] ?? "";
}

function handleSort(col: RTableColumn) {
  if (!col.sortable) return;
  // Toggle direction when re-clicking the active column; new column
  // starts at ascending (mirrors VDataTable behaviour).
  const nextDir: RTableSortDir =
    props.sortKey === col.key && props.sortDir === "asc" ? "desc" : "asc";
  emit("update:sort", { key: col.key, dir: nextDir });
}

const rowStyle = computed(() =>
  props.rowHeight ? { height: props.rowHeight } : undefined,
);
</script>

<template>
  <div class="r-table" v-bind="$attrs">
    <!-- Header row — each column header is a cell `<div>` containing
         either a sort `<button>` (sortable cols) or a plain label, plus
         an optional `header.<key>` slot for adornments (e.g. a help
         icon next to "Type"). The sort button is the only interactive
         element so adornments stay focusable / clickable on their own
         without nesting buttons. -->
    <div class="r-table__scroll" :style="scrollStyle">
      <div class="r-table__header" :style="gridStyle" role="row">
        <div
          v-for="col in columns"
          :key="col.key"
          class="r-table__header-cell"
          :class="{
            'r-table__header-cell--end': col.align === 'end',
            'r-table__header-cell--center': col.align === 'center',
          }"
          role="columnheader"
          :aria-sort="
            col.sortable && sortKey === col.key
              ? sortDir === 'asc'
                ? 'ascending'
                : 'descending'
              : col.sortable
                ? 'none'
                : undefined
          "
        >
          <button
            v-if="col.sortable"
            type="button"
            class="r-table__header-sort"
            :class="{
              'r-table__header-sort--active': sortKey === col.key,
            }"
            @click="handleSort(col)"
          >
            <span class="r-table__header-label">{{ col.label }}</span>
            <RIcon
              v-if="sortKey === col.key"
              :icon="
                sortDir === 'asc' ? 'mdi-arrow-up-thin' : 'mdi-arrow-down-thin'
              "
              size="14"
              class="r-table__header-icon"
            />
          </button>
          <span v-else class="r-table__header-label">{{ col.label }}</span>

          <slot :name="`header.${col.key}`" :column="col" />
        </div>
      </div>

      <!-- Body — skeletons / real rows / empty state, in that order. -->
      <div class="r-table__body">
        <template v-if="loading">
          <div
            v-for="i in loadingRows"
            :key="`skel-${i}`"
            class="r-table__row r-table__row--skeleton"
            :style="[gridStyle, rowStyle ?? {}]"
          >
            <template v-for="col in columns" :key="col.key">
              <div
                class="r-table__cell"
                :class="{
                  'r-table__cell--end': col.align === 'end',
                  'r-table__cell--center': col.align === 'center',
                }"
              >
                <RSkeletonBlock
                  v-if="col.skeletonWidth !== 0"
                  :width="col.skeletonWidth ?? 80"
                  :height="10"
                />
              </div>
            </template>
          </div>
        </template>

        <template v-else-if="items.length === 0">
          <div class="r-table__empty">
            <slot name="empty">
              <RIcon :icon="emptyIcon" size="32" />
              <span v-if="emptyMessage" class="r-table__empty-text">
                {{ emptyMessage }}
              </span>
            </slot>
          </div>
        </template>

        <template v-else>
          <!-- eslint-disable-next-line vuejs-accessibility/interactive-supports-focus -->
          <div
            v-for="(row, idx) in items"
            :key="rowKey(row, idx)"
            class="r-table__row"
            :class="[
              { 'r-table__row--clickable': clickableRows },
              rowClassFor(row),
            ]"
            :style="[gridStyle, rowStyle ?? {}]"
            role="row"
            :tabindex="clickableRows ? 0 : -1"
            @click="clickableRows && emit('row:click', row)"
            @keydown.enter.space.prevent="
              clickableRows && emit('row:click', row)
            "
          >
            <div
              v-for="col in columns"
              :key="col.key"
              class="r-table__cell"
              :class="{
                'r-table__cell--end': col.align === 'end',
                'r-table__cell--center': col.align === 'center',
              }"
              role="cell"
            >
              <slot
                :name="`cell.${col.key}`"
                :row="row"
                :column="col"
                :index="idx"
              >
                {{ cellValue(row, col.key) }}
              </slot>
            </div>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<style scoped>
.r-table {
  border: 1px solid var(--r-color-border);
  border-radius: 10px;
  overflow: hidden;
  background: var(--r-color-bg-elevated);
  display: flex;
  flex-direction: column;
}

/* Horizontal-scroll viewport — header + body scroll together so their
   columns stay aligned. Inert until a `minWidth` is set (the var defaults
   to 0, so the grids just fill the width as before). */
.r-table__scroll {
  overflow-x: auto;
  scrollbar-width: thin;
}
.r-table__header,
.r-table__body {
  min-width: var(--r-table-min-w, 0);
}

/* ------------------------- Header ------------------------- */
.r-table__header {
  display: grid;
  align-items: center;
  gap: 0 var(--r-space-3);
  padding: 0 var(--r-space-3);
  height: var(--r-list-header-h, 38px);
  background: var(--r-color-surface);
  border-bottom: 1px solid var(--r-color-border);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
}

/* Outer cell — flex container holding the sort button (or static
   label) and any consumer adornment from the `header.<key>` slot. */
.r-table__header-cell {
  display: inline-flex;
  align-items: center;
  gap: var(--r-space-1, 4px);
  min-width: 0;
  height: 100%;
  color: var(--r-color-fg-muted);
  font-size: var(--r-font-size-xs, 10px);
  font-weight: var(--r-font-weight-bold);
  letter-spacing: 0.07em;
  text-transform: uppercase;
}
.r-table__header-cell--end {
  justify-content: flex-end;
  text-align: end;
}
.r-table__header-cell--center {
  justify-content: center;
  text-align: center;
}

/* Inner sort button — the only interactive piece in the header. The
   tint flips to fg on hover/focus/active so the affordance still reads
   exactly like the previous all-cell button. */
.r-table__header-sort {
  appearance: none;
  background: transparent;
  border: 0;
  padding: 0;
  font: inherit;
  color: inherit;
  display: inline-flex;
  align-items: center;
  gap: var(--r-space-1, 4px);
  min-width: 0;
  cursor: pointer;
  text-align: inherit;
  text-transform: inherit;
  letter-spacing: inherit;
  border-radius: var(--r-radius-sm);
  transition: color var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-table__header-sort:hover,
.r-table__header-sort:focus-visible {
  color: var(--r-color-fg);
}
.r-table__header-sort--active {
  color: var(--r-color-fg);
}

.r-table__header-label {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.r-table__header-icon {
  flex-shrink: 0;
  color: var(--r-color-brand-primary);
}

/* ------------------------- Body --------------------------- */
.r-table__body {
  display: flex;
  flex-direction: column;
}

.r-table__row {
  display: grid;
  align-items: center;
  gap: 0 var(--r-space-3);
  padding: 0 var(--r-space-3);
  height: var(--r-list-row-h, 56px);
  border-bottom: 1px solid var(--r-color-border);
  font-size: 13px;
  color: var(--r-color-fg);
  transition: background var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-table__row:last-child {
  border-bottom: none;
}
.r-table__row:hover {
  background: var(--r-color-surface);
}
.r-table__row--clickable {
  cursor: pointer;
}

.r-table__cell {
  min-width: 0;
  min-height: 50px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  display: flex;
  align-items: center;
  gap: var(--r-space-1, 4px);
}
.r-table__cell--end {
  justify-content: flex-end;
}
.r-table__cell--center {
  justify-content: center;
}

/* ----------------------- Empty state ---------------------- */
.r-table__empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 32px 16px;
  color: var(--r-color-fg-muted);
  text-align: center;
}
.r-table__empty-text {
  font-size: 13px;
}
</style>
