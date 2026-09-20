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
import { RCheckbox, RIcon, RMenu, RMenuItem } from "@v2/lib";
import { computed } from "vue";
import { useI18n } from "vue-i18n";
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
  sortDir: "asc" | "desc";
  /** Include the `platform` column. True on cross-platform surfaces
   * (Search / Collection / Missing games); false on Platform.vue where
   * every row shares the same platform. Mirrors the prop of the same
   * name on `GameListRow` + `GameListSkeletonRow` so all three stay in
   * lockstep. */
  showPlatformColumn?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
  showPlatformColumn: true,
});

const emit = defineEmits<{
  (e: "sort", payload: { key: ListSortKey; dir: "asc" | "desc" }): void;
}>();

const { t } = useI18n();
const columns = computed(() => getListColumns(props.showPlatformColumn));
const gridStyle = computed(() => ({
  gridTemplateColumns: getListGridTemplate(props.showPlatformColumn),
}));

// Phones and tablets drop the columns (the rows go compact), so the sort
// key they used to carry moves into a menu on the header.
const { smAndDown } = useBreakpoint();
const compact = computed(() => smAndDown.value);
const sortOptions = computed(() => getSortOptions(props.showPlatformColumn));
const sortLabel = computed(
  () =>
    sortOptions.value.find((option) => option.key === props.sortKey)?.label ??
    sortOptions.value[0]?.label ??
    "",
);

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

function sortBy(key: ListSortKey) {
  // Toggle direction when re-picking the active key; otherwise start the
  // new one ascending, like every other sortable table in the app.
  const nextDir: "asc" | "desc" =
    props.sortKey === key && props.sortDir === "asc" ? "desc" : "asc";
  emit("sort", { key, dir: nextDir });
}

function handleClick(col: ListColumn) {
  if (isSortableColumn(col)) sortBy(col.key);
}
</script>

<template>
  <div
    v-if="compact"
    class="game-list-header game-list-header--compact"
    role="row"
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

    <RMenu location="bottom start" :offset="6" sheet-on-mobile>
      <template #activator="{ props: activatorProps }">
        <button
          v-bind="activatorProps"
          type="button"
          class="game-list-header__cell game-list-header__cell--sortable game-list-header__cell--active"
        >
          <span class="game-list-header__label">{{ sortLabel }}</span>
          <RIcon
            :icon="
              sortDir === 'asc' ? 'mdi-arrow-up-thin' : 'mdi-arrow-down-thin'
            "
            size="14"
            class="game-list-header__icon"
          />
        </button>
      </template>
      <RMenuItem
        v-for="option in sortOptions"
        :key="String(option.key)"
        :label="option.label"
        :variant="sortKey === option.key ? 'active' : 'default'"
        @click="sortBy(option.key)"
      >
        <template #append>
          <RIcon
            v-if="sortKey === option.key"
            :icon="
              sortDir === 'asc' ? 'mdi-arrow-up-thin' : 'mdi-arrow-down-thin'
            "
            size="14"
            class="game-list-header__icon"
          />
        </template>
      </RMenuItem>
    </RMenu>
  </div>

  <div v-else class="game-list-header" :style="gridStyle" role="row">
    <template v-for="col in columns" :key="String(col.key)">
      <!-- Tri-state select-all checkbox (off → some → all), judged
           against the whole filtered result. -->
      <RCheckbox
        v-if="col.key === 'select'"
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

      <button
        v-else
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
          :icon="
            sortDir === 'asc' ? 'mdi-arrow-up-thin' : 'mdi-arrow-down-thin'
          "
          size="14"
          class="game-list-header__icon"
        />
      </button>
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
  width: var(--r-list-select-w, 36px);
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

/* End-aligned labels hug the right edge, so the sort glyph goes on the
   label's left. Appending it would shove the label sideways on click. */
.game-list-header__cell--end .game-list-header__icon {
  order: -1;
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

/* Select-all checkbox in the leading column: RCheckbox bare/circle, matching the
   GameCard and GameListRow ticks, and centred over every row's tick. */
.game-list-header__check {
  justify-self: center;
}
</style>
