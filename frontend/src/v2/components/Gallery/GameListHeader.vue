<script setup lang="ts">
// GameListHeader: sticky column-header row for list-mode galleries.
//
// Layout: a single CSS-grid div sharing `LIST_GRID_TEMPLATE` with every
// `GameListRow` underneath, so columns line up regardless of viewport.
// Click on a sortable column toggles asc → desc → asc (single-key sort,
// matching the rest of the gallery surface), or asc → desc → unsorted when
// the gallery has an order of its own to fall back to.
//
// Sticky positioning is owned by the parent (`GalleryShell` pins this
// below the toolbar at `top: --r-v2-shell-toolbar-h`). The header
// itself only paints: it doesn't manage scroll.
import { RCheckbox, RSortHeader, type RSortDir } from "@v2/lib";
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import ListSortMenu from "@/v2/components/shared/ListSortMenu.vue";
import { useBreakpoint } from "@/v2/composables/useBreakpoint";
import { useGallerySelectAll } from "@/v2/composables/useGallerySelectAll";
import storeGallerySelection from "@/v2/stores/gallerySelection";
import {
  getListColumns,
  getSortOptions,
  isSortableColumn,
  getListGridTemplate,
  type ListColumn,
  type ListSortKey,
} from "./listColumns";

interface Props {
  /** Currently-sorted column key. `null` when no sort is active. */
  sortKey: ListSortKey | null;
  /** Sort direction for the active key. */
  sortDir: RSortDir;
  /** Include the `platform` column. True on cross-platform surfaces
   * (Search / Collection / Missing games); false on Platform.vue where
   * every row shares the same platform. Mirrors the prop of the same
   * name on `GameListRow` + `GameListSkeletonRow` so all three stay in
   * lockstep. */
  showPlatformColumn?: boolean;
  /** Names the gallery's order without a sort key (Search's relevance), and
   * lets a third click on a column return to it. */
  unsortedLabel?: string | undefined;
  /** Whether that order is the one applied. */
  unsorted?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
  showPlatformColumn: true,
  unsortedLabel: undefined,
  unsorted: false,
});

const emit = defineEmits<{
  (e: "sort", payload: { key: ListSortKey; dir: RSortDir }): void;
  (e: "unsort"): void;
}>();

const { t } = useI18n();
const columns = computed(() => getListColumns(props.showPlatformColumn));
const gridStyle = computed(() => ({
  gridTemplateColumns: getListGridTemplate(props.showPlatformColumn),
}));

// Phones and tablets drop the columns (the rows go compact), so the sort
// key they used to carry moves into a menu on the header.
const { smAndDown } = useBreakpoint();
const sortOptions = computed(() => getSortOptions(props.showPlatformColumn));

const selection = storeGallerySelection();
// Whole-result select-all shared with the SelectionBar and Ctrl/Cmd+A;
// `selectionState` drives the tri-state checkbox glyph.
const { selectionState, selectAll } = useGallerySelectAll();

function onSelectAllClick(e: MouseEvent) {
  e.preventDefault();
  e.stopPropagation();
  // Indeterminate behaves like "off → all" (typical file-manager UX:
  // a tri-state checkbox click resolves to "all checked").
  if (selectionState.value === "all") {
    selection.clear();
  } else {
    void selectAll();
  }
}

function onSort(col: ListColumn, dir: RSortDir) {
  if (!isSortableColumn(col)) return;
  if (
    props.unsortedLabel &&
    props.sortKey === col.key &&
    props.sortDir === "desc"
  ) {
    emit("unsort");
    return;
  }
  emit("sort", { key: col.key, dir });
}
</script>

<template>
  <div v-if="smAndDown" class="game-list-header game-list-header--compact">
    <RCheckbox
      class="game-list-header__check"
      :model-value="selectionState === 'all'"
      :indeterminate="selectionState === 'some'"
      shape="circle"
      size="sm"
      color="primary"
      bare
      hide-details
      :aria-label="
        selectionState === 'all'
          ? t('gallery.selection-deselect-all')
          : t('gallery.selection-select-all')
      "
      @click="onSelectAllClick"
    />

    <ListSortMenu
      :options="sortOptions"
      :sort-key="sortKey"
      :sort-dir="sortDir"
      :unsorted-label="unsortedLabel"
      :unsorted="unsorted"
      @sort="emit('sort', $event)"
      @unsort="emit('unsort')"
    />
  </div>

  <div v-else class="game-list-header" :style="gridStyle" role="row">
    <template v-for="col in columns" :key="String(col.key)">
      <!-- Tri-state select-all checkbox (off → some → all), judged
           against the whole filtered result. -->
      <div
        v-if="col.key === 'select'"
        role="columnheader"
        class="game-list-header__select"
      >
        <RCheckbox
          class="game-list-header__check"
          :model-value="selectionState === 'all'"
          :indeterminate="selectionState === 'some'"
          shape="circle"
          size="sm"
          color="primary"
          bare
          hide-details
          :aria-label="
            selectionState === 'all'
              ? t('gallery.selection-deselect-all')
              : t('gallery.selection-select-all')
          "
          @click="onSelectAllClick"
        />
      </div>
      <RSortHeader
        v-else
        :label="col.label || col.hiddenLabel || ''"
        :hide-label="!col.label"
        :sortable="col.sortable"
        :active="sortKey === col.key"
        :dir="sortDir"
        :align="col.align"
        @sort="onSort(col, $event)"
      />
    </template>
  </div>
</template>

<style scoped>
.game-list-header {
  display: grid;
  align-items: center;
  gap: 0 var(--r-space-5);
  padding: 0 var(--r-space-3);
  height: var(--r-list-header-h);
  /* Overridable so a pinned header can run it edge to edge (r-pinned-list-header). */
  border-bottom: var(--r-list-header-border, 1px solid var(--r-color-border));
}

/* Compact (phones / tablets): the tick plus one sort control. */
.game-list-header--compact {
  display: flex;
  align-items: center;
  gap: var(--r-space-3);
  padding: 0 var(--r-row-pad);
}
.game-list-header--compact .game-list-header__check {
  flex: none;
  width: var(--r-list-select-w);
}

.game-list-header__select {
  display: flex;
  justify-content: center;
  min-width: 0;
  height: 100%;
}

/* Select-all checkbox in the leading column: RCheckbox bare/circle, matching the
   GameCard and GameListRow ticks, and centred over every row's tick. */
.game-list-header__check {
  align-self: center;
}
</style>
