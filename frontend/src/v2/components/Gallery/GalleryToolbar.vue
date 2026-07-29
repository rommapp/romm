<script setup lang="ts">
// GalleryToolbar — the "how should I see these games?" control strip for
// Platform / Collection / Search views.
//
// Controlled externally via `useGalleryMode()`; the parent passes the refs
// in so this stays presentational.
//
// `position="header"` renders inline in the content flow, full width, with
// controls right-aligned. `position="floating"` docks it top-right of the
// gallery's scroll container as a glass pill.
import {
  RBadge,
  RBtn,
  RDivider,
  RIcon,
  RMenu,
  RMenuItem,
  RSliderBtnGroup,
  RTextField,
} from "@v2/lib";
import type { Ref } from "vue";
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import { useBreakpoint } from "@/v2/composables/useBreakpoint";
import type {
  GroupByMode,
  LayoutMode,
  ToolbarPosition,
} from "@/v2/composables/useGalleryMode";

defineOptions({ inheritAttrs: false });

const { t } = useI18n();

export interface SegmentFilterItem {
  id: string;
  icon?: string;
  label?: string;
  ariaLabel?: string;
  title?: string;
}
/** A segmented-filter cluster (e.g. kind, visibility). The toolbar renders
 *  one inline slider per entry (≥ sm) and mirrors each into the kebab menu
 *  below it; `key` identifies which cluster fired in `update:segmentFilter`. */
export interface SegmentFilter {
  key: string;
  value: string;
  items: SegmentFilterItem[];
  ariaLabel?: string;
  /** Dim the whole cluster and block changes (e.g. visibility when the
   *  kind filter is on "virtual", which has no visibility state). */
  disabled?: boolean;
}

export interface GroupByItem {
  id: GroupByMode;
  icon?: string;
  label?: string;
  ariaLabel?: string;
  title?: string;
}

const props = withDefaults(
  defineProps<{
    groupBy: Ref<GroupByMode> | GroupByMode;
    layout: Ref<LayoutMode> | LayoutMode;
    position?: ToolbarPosition;
    /** Show the GroupBy toggle (hide it on views where grouping doesn't make sense). */
    showGroupBy?: boolean;
    /** Override the GroupBy options — used by index views (Platforms)
     *  to expose richer modes (family / category / generation) beyond
     *  the default flat / letter pair. */
    groupByItems?: GroupByItem[];
    /** Direction toggle for grid-mode sort. Disabled in list mode
     *  (list-mode sort is driven by the column-header clicks). */
    sortDir?: Ref<"asc" | "desc"> | "asc" | "desc";
    /** Show the search field on the left. v-model:search controls its value. */
    showSearch?: boolean;
    search?: string;
    searchPlaceholder?: string;
    /** Segmented filter clusters (sit left of the view cluster). Used by
     *  CollectionsIndex for the kind + visibility filters. Each renders as
     *  an inline slider (≥ sm) and mirrors into the kebab menu below it. */
    segmentFilters?: SegmentFilter[];
    /** Show the filter button (sits left of the view cluster). When set,
     *  the button emits `click:filter` and renders a badge of the count.
     *  Gallery views pass through the count from the filter store. */
    showFilter?: boolean;
    filterActiveCount?: number;
  }>(),
  {
    position: "header",
    showGroupBy: true,
    // Default groupBy items live in a setup-scope computed
    // (`defaultGroupByItems`) so labels go through `t()`. The
    // `withDefaults` factory is hoisted outside `setup()` and cannot
    // reference identifiers, so we leave the default empty here and
    // substitute downstream through `effectiveGroupByItems`.
    groupByItems: () => [],
    sortDir: "asc",
    showSearch: false,
    search: "",
    searchPlaceholder: "",
    segmentFilters: () => [],
    showFilter: false,
    filterActiveCount: 0,
  },
);

const emit = defineEmits<{
  (e: "update:groupBy", value: GroupByMode): void;
  (e: "update:layout", value: LayoutMode): void;
  (e: "update:sortDir", value: "asc" | "desc"): void;
  (e: "update:search", value: string): void;
  (e: "update:segmentFilter", payload: { key: string; value: string }): void;
  (e: "click:filter"): void;
}>();

// Support both a Ref or a plain value — keeps consumption flexible.
function toValue<T>(source: Ref<T> | T): T {
  return source && typeof source === "object" && "value" in (source as object)
    ? ((source as Ref<T>).value as T)
    : (source as T);
}

const groupByValue = computed(() => toValue(props.groupBy));
const layoutValue = computed(() => toValue(props.layout));
const sortDirValue = computed(() => toValue(props.sortDir));

const layoutItems = computed(() => [
  {
    id: "grid" as const,
    icon: "mdi-view-grid-outline",
    ariaLabel: t("gallery.view-grid"),
    title: t("gallery.view-grid"),
  },
  {
    id: "list" as const,
    icon: "mdi-view-list",
    ariaLabel: t("gallery.view-list"),
    title: t("gallery.view-list"),
  },
]);

const sortDirItems = computed(() => [
  {
    id: "asc" as const,
    icon: "mdi-sort-ascending",
    ariaLabel: t("gallery.sort-ascending"),
    title: t("gallery.sort-ascending"),
  },
  {
    id: "desc" as const,
    icon: "mdi-sort-descending",
    ariaLabel: t("gallery.sort-descending"),
    title: t("gallery.sort-descending"),
  },
]);

// Default group-by items (used when the parent doesn't override
// `groupByItems`). Computed so the labels track the active locale.
const defaultGroupByItems = computed<GroupByItem[]>(() => [
  {
    id: "none",
    icon: "mdi-view-agenda-outline",
    ariaLabel: t("gallery.view-flat"),
    title: t("gallery.view-flat"),
  },
  {
    id: "letter",
    icon: "mdi-alphabetical-variant",
    ariaLabel: t("gallery.view-grouped"),
    title: t("gallery.view-grouped"),
  },
]);

const effectiveGroupByItems = computed<GroupByItem[]>(() =>
  props.groupByItems.length > 0
    ? props.groupByItems
    : defaultGroupByItems.value,
);

const effectiveSearchPlaceholder = computed(
  () => props.searchPlaceholder || `${t("common.search")}…`,
);

function setGroupBy(value: GroupByMode) {
  emit("update:groupBy", value);
}

function setLayout(value: LayoutMode) {
  emit("update:layout", value);
}

function setSortDir(value: "asc" | "desc") {
  emit("update:sortDir", value);
}

function setSearch(value: string) {
  emit("update:search", value);
}

function setSegmentFilter(key: string, value: string) {
  emit("update:segmentFilter", { key, value });
}

// Responsive split: at ≥ smAndUp (600px) the inline sliders carry every
// view option; below that they collapse into the kebab menu so the
// toolbar fits on phones without overflowing. Mutually exclusive so the
// two paths never paint at the same time.
const { smAndUp } = useBreakpoint();
</script>

<template>
  <div class="gallery-toolbar" :class="[`gallery-toolbar--${position}`]">
    <!-- Filter controls. Always sits left of the controls cluster. -->
    <RTextField
      v-if="showSearch"
      :model-value="search"
      :placeholder="effectiveSearchPlaceholder"
      density="comfortable"
      prefix-label="inline"
      clearable
      hide-details
      class="gallery-toolbar__search"
      @update:model-value="(v: string) => setSearch(v ?? '')"
    >
      <template #prefix-label>
        <RIcon icon="mdi-magnify" size="16" />
      </template>
    </RTextField>

    <!-- Filter button — sits flush against the search field. Same disc
         shape as the kebab (outlined icon-only RBtn); the active-count
         chip is `RBadge` anchored top-end. -->
    <RBadge
      v-if="showFilter"
      :model-value="filterActiveCount > 0"
      :content="filterActiveCount"
      color="primary"
      floating
    >
      <RBtn
        variant="outlined"
        surface
        icon="mdi-filter-variant"
        rounded="circle"
        :aria-label="t('gallery.filters')"
        @click="emit('click:filter')"
      />
    </RBadge>

    <template v-if="smAndUp">
      <RSliderBtnGroup
        v-for="sf in segmentFilters"
        :key="sf.key"
        :model-value="sf.value"
        :items="sf.items"
        variant="segmented"
        :aria-label="sf.ariaLabel"
        :disabled="sf.disabled"
        @update:model-value="(v: string) => setSegmentFilter(sf.key, v)"
      />
    </template>

    <!-- View controls cluster — pushed right via margin-left: auto.
         At ≥ smAndUp the inline sliders carry every option; below that
         they collapse into the kebab menu so the toolbar fits on phones
         without overflowing. -->
    <div class="gallery-toolbar__controls">
      <RSliderBtnGroup
        v-if="smAndUp && showGroupBy"
        :model-value="groupByValue"
        :items="effectiveGroupByItems"
        variant="segmented"
        :aria-label="t('settings.platforms-drawer-group-by')"
        :disabled="layoutValue === 'list'"
        @update:model-value="setGroupBy"
      />

      <RSliderBtnGroup
        v-if="smAndUp"
        :model-value="sortDirValue"
        :items="sortDirItems"
        variant="segmented"
        :aria-label="t('gallery.sort-ascending')"
        :disabled="layoutValue === 'list'"
        @update:model-value="setSortDir"
      />

      <RSliderBtnGroup
        v-if="smAndUp"
        :model-value="layoutValue"
        :items="layoutItems"
        variant="segmented"
        :aria-label="t('common.type')"
        @update:model-value="setLayout"
      />

      <!-- Kebab mirror — only visible below smAndUp. Mirrors the slider
           state: `groupBy` items disable in list mode, same way the
           inline GroupBy slider does. -->
      <RMenu
        v-if="!smAndUp"
        location="bottom end"
        :offset="8"
        width="220px"
        sheet-on-mobile
      >
        <template #activator="{ props: activatorProps }">
          <RBtn
            v-bind="activatorProps"
            variant="outlined"
            surface
            icon="mdi-dots-vertical"
            rounded="circle"
            :aria-label="t('platform.change-view')"
          />
        </template>
        <template v-for="sf in segmentFilters" :key="sf.key">
          <RMenuItem
            v-for="item in sf.items"
            :key="item.id"
            :label="item.label ?? item.title ?? item.ariaLabel ?? item.id"
            :icon="item.icon"
            :variant="sf.value === item.id ? 'active' : 'default'"
            :disabled="sf.disabled"
            @click="setSegmentFilter(sf.key, item.id)"
          />
          <RDivider />
        </template>
        <template v-if="showGroupBy && effectiveGroupByItems.length > 0">
          <RMenuItem
            v-for="item in effectiveGroupByItems"
            :key="item.id"
            :label="item.label ?? item.title ?? item.ariaLabel ?? item.id"
            :icon="item.icon"
            :variant="groupByValue === item.id ? 'active' : 'default'"
            :disabled="layoutValue === 'list'"
            @click="setGroupBy(item.id)"
          />
          <RDivider />
        </template>
        <RMenuItem
          :label="t('gallery.sort-ascending')"
          icon="mdi-sort-ascending"
          :variant="sortDirValue === 'asc' ? 'active' : 'default'"
          :disabled="layoutValue === 'list'"
          @click="setSortDir('asc')"
        />
        <RMenuItem
          :label="t('gallery.sort-descending')"
          icon="mdi-sort-descending"
          :variant="sortDirValue === 'desc' ? 'active' : 'default'"
          :disabled="layoutValue === 'list'"
          @click="setSortDir('desc')"
        />
        <RDivider />
        <RMenuItem
          :label="t('gallery.view-grid')"
          icon="mdi-view-grid-outline"
          :variant="layoutValue === 'grid' ? 'active' : 'default'"
          @click="setLayout('grid')"
        />
        <RMenuItem
          :label="t('gallery.view-list')"
          icon="mdi-view-list"
          :variant="layoutValue === 'list' ? 'active' : 'default'"
          @click="setLayout('list')"
        />
      </RMenu>
    </div>
  </div>
</template>

<style scoped>
.gallery-toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
}

/* Header variant — full width, search on the left, controls right.
   Margin lives here (not on the consumer) so scoped-style precedence never
   prevents the toolbar from breathing against the content below. */
.gallery-toolbar--header {
  width: 100%;
  margin: var(--r-space-2) 0 var(--r-space-6);
}

/* Floating variant — fixed top-right of the gallery body. */
.gallery-toolbar--floating {
  position: absolute;
  top: 14px;
  right: 14px;
  z-index: 5;
  padding: 4px;
  background: var(--r-color-bg-elevated);
  border: 1px solid var(--r-color-border);
  border-radius: var(--r-radius-pill);
  backdrop-filter: blur(20px);
}

/* Controls cluster — gets pushed right by its own margin. */
.gallery-toolbar__controls {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-left: auto;
}

/* Search — bounded width so the pills stay visible on wide screens. */
.gallery-toolbar__search {
  flex: 0 1 360px;
  min-width: 0;
}
</style>
