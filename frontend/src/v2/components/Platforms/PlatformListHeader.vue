<script setup lang="ts">
// PlatformListHeader — column-header strip for the Platforms list-mode
// view. Mirrors GameListHeader: shared CSS-grid template with every
// row underneath, clickable sortable columns that toggle asc → desc.
//
// Phones and tablets have no columns to head (the rows go compact), so the
// sort key they carried moves into a menu, same as the collections list.
import { RIcon } from "@v2/lib";
import { computed } from "vue";
import ListSortMenu from "@/v2/components/shared/ListSortMenu.vue";
import { useBreakpoint } from "@/v2/composables/useBreakpoint";
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

const { smAndDown } = useBreakpoint();
const sortOptions = computed(() =>
  PLATFORM_COLUMNS.filter((col) => col.sortable).map((col) => ({
    key: col.key,
    label: col.label,
  })),
);

function handleClick(col: PlatformColumn) {
  if (!col.sortable) return;
  const nextDir: "asc" | "desc" =
    props.sortKey === col.key && props.sortDir === "asc" ? "desc" : "asc";
  emit("sort", { key: col.key, dir: nextDir });
}
</script>

<template>
  <div
    v-if="smAndDown"
    class="plat-list-header plat-list-header--compact"
    role="row"
  >
    <ListSortMenu
      :options="sortOptions"
      :sort-key="sortKey"
      :sort-dir="sortDir"
      @sort="emit('sort', $event)"
    />
  </div>

  <div v-else class="plat-list-header" role="row">
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
  padding: 0 max(var(--r-space-3), var(--r-list-bleed, 0px));
  height: var(--r-list-header-h);
  /* Overridable so a pinned header can run it edge to edge (r-pinned-list-header). */
  border-bottom: var(--r-list-header-border, 1px solid var(--r-color-border));
}

/* Compact (phones / tablets): one sort control instead of the columns. */
.plat-list-header--compact {
  display: flex;
  align-items: center;
  padding: 0 var(--r-row-pad);
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
</style>
