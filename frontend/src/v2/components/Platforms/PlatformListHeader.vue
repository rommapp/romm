<script setup lang="ts">
// PlatformListHeader: column-header strip for the Platforms list-mode
// view. Mirrors GameListHeader: shared CSS-grid template with every
// row underneath, clickable sortable columns that toggle asc → desc.
//
// Phones and tablets have no columns to head (the rows go compact), so the
// sort key they carried moves into a menu, same as the collections list.
import { RSortHeader, type RSortDir } from "@v2/lib";
import { computed } from "vue";
import ListSortMenu from "@/v2/components/shared/ListSortMenu.vue";
import { useBreakpoint } from "@/v2/composables/useBreakpoint";
import { PLATFORM_COLUMNS, type PlatformSortKey } from "./platformListColumns";

interface Props {
  sortKey: PlatformSortKey;
  sortDir: RSortDir;
}

defineProps<Props>();

const emit = defineEmits<{
  (e: "sort", payload: { key: PlatformSortKey; dir: RSortDir }): void;
}>();

const { smAndDown } = useBreakpoint();
const sortOptions = computed(() =>
  PLATFORM_COLUMNS.filter((col) => col.sortable).map((col) => ({
    key: col.key,
    label: col.label,
  })),
);
</script>

<template>
  <div v-if="smAndDown" class="plat-list-header plat-list-header--compact">
    <ListSortMenu
      :options="sortOptions"
      :sort-key="sortKey"
      :sort-dir="sortDir"
      @sort="emit('sort', $event)"
    />
  </div>

  <div v-else class="plat-list-header" role="row">
    <RSortHeader
      v-for="col in PLATFORM_COLUMNS"
      :key="col.key"
      :label="col.label"
      :sortable="col.sortable"
      :active="sortKey === col.key"
      :dir="sortDir"
      :align="col.align"
      @sort="emit('sort', { key: col.key, dir: $event })"
    />
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
</style>
