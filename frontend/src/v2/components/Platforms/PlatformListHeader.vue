<script setup lang="ts">
// PlatformListHeader — column-header strip for the Platforms list-mode
// view. Mirrors GameListHeader: shared CSS-grid template with every
// row underneath, clickable sortable columns that toggle asc → desc.
//
// The four metadata columns (Family / Category / Generation / Playable)
// drop out on narrow viewports (see the `html[data-bp~="xs"]` rules
// below) so the row stays legible on mobile without horizontal scroll.
// The grid template flips in the same breakpoint so the cells re-align
// with the row's compact layout.
import { RIcon } from "@v2/lib";
import {
  PLATFORM_COLUMNS,
  type PlatformColumn,
  type PlatformSortKey,
} from "./platformListColumns";

interface Props {
  sortKey: PlatformSortKey;
  sortDir: "asc" | "desc";
}

const props = defineProps<Props>();

const emit = defineEmits<{
  (e: "sort", payload: { key: PlatformSortKey; dir: "asc" | "desc" }): void;
}>();

function handleClick(col: PlatformColumn) {
  if (!col.sortable) return;
  const nextDir: "asc" | "desc" =
    props.sortKey === col.key && props.sortDir === "asc" ? "desc" : "asc";
  emit("sort", { key: col.key, dir: nextDir });
}
</script>

<template>
  <div class="plat-list-header" role="row">
    <button
      v-for="col in PLATFORM_COLUMNS"
      :key="col.key"
      type="button"
      class="plat-list-header__cell"
      :class="{
        'plat-list-header__cell--meta': col.meta,
        'plat-list-header__cell--sortable': col.sortable,
        'plat-list-header__cell--end': col.align === 'end',
        'plat-list-header__cell--center': col.align === 'center',
        'plat-list-header__cell--active': col.sortable && sortKey === col.key,
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
      <span class="plat-list-header__label">{{ col.label }}</span>
      <RIcon
        v-if="col.sortable && sortKey === col.key"
        :icon="sortDir === 'asc' ? 'mdi-arrow-up-thin' : 'mdi-arrow-down-thin'"
        size="14"
        class="plat-list-header__icon"
      />
    </button>
  </div>
</template>

<style scoped>
.plat-list-header {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 160px 130px 110px 88px 96px;
  align-items: center;
  gap: 0 var(--r-space-3);
  padding: 0 var(--r-space-3);
  height: var(--r-list-header-h);
  background: var(--r-color-bg-elevated);
  border-bottom: 1px solid var(--r-color-border);
}

.plat-list-header__cell {
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

.plat-list-header__cell--end {
  justify-content: flex-end;
  text-align: end;
}
.plat-list-header__cell--center {
  justify-content: center;
  text-align: center;
}

.plat-list-header__cell--sortable {
  cursor: pointer;
}

.plat-list-header__cell--sortable:hover,
.plat-list-header__cell--sortable:focus-visible {
  color: var(--r-color-fg);
}

.plat-list-header__cell--active {
  color: var(--r-color-fg);
}

.plat-list-header__label {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.plat-list-header__icon {
  flex-shrink: 0;
  color: var(--r-color-brand-primary);
}

html[data-bp~="xs"] .plat-list-header {
  grid-template-columns: minmax(0, 1fr) 96px;
}
html[data-bp~="xs"] .plat-list-header__cell--meta {
  display: none;
}
</style>
