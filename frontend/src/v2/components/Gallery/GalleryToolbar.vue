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
import { useBreakpoint } from "@/v2/composables/useBreakpoint";
import type {
  GroupByMode,
  LayoutMode,
  ToolbarPosition,
} from "@/v2/composables/useGalleryMode";

defineOptions({ inheritAttrs: false });

export type KindFilterValue = "all" | "regular" | "virtual";
export interface KindFilterItem {
  id: KindFilterValue;
  icon?: string;
  label?: string;
  ariaLabel?: string;
  title?: string;
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
    /** Show the search field on the left. v-model:search controls its value. */
    showSearch?: boolean;
    search?: string;
    searchPlaceholder?: string;
    /** Show the kind filter (sits left of GroupBy). Used by CollectionsIndex
     *  to switch between all / non-virtual / virtual collections. */
    showKindFilter?: boolean;
    kindFilter?: KindFilterValue;
    kindFilterItems?: KindFilterItem[];
    kindFilterAriaLabel?: string;
    /** Show the filter button (sits left of the view cluster). When set,
     *  the button emits `click:filter` and renders a badge of the count.
     *  Gallery views pass through the count from the filter store. */
    showFilter?: boolean;
    filterActiveCount?: number;
  }>(),
  {
    position: "header",
    showGroupBy: true,
    // Inline default — flat + by-letter, the universal pair every
    // gallery surface (Platform / Collection / Search) supports. Index
    // views (PlatformsIndex) override this with a richer list. Cannot
    // reference an outer const here: `withDefaults`' factory is hoisted
    // outside `setup()`, so any module-scope identifier it touched
    // would explode at compile time.
    groupByItems: () => [
      {
        id: "none",
        icon: "mdi-view-agenda-outline",
        ariaLabel: "Flat view",
        title: "Flat view",
      },
      {
        id: "letter",
        icon: "mdi-alphabetical-variant",
        ariaLabel: "Group by letter",
        title: "Group by letter",
      },
    ],
    showSearch: false,
    search: "",
    searchPlaceholder: "Search…",
    showKindFilter: false,
    kindFilter: "all",
    kindFilterItems: () => [],
    kindFilterAriaLabel: "Filter by kind",
    showFilter: false,
    filterActiveCount: 0,
  },
);

const emit = defineEmits<{
  (e: "update:groupBy", value: GroupByMode): void;
  (e: "update:layout", value: LayoutMode): void;
  (e: "update:search", value: string): void;
  (e: "update:kindFilter", value: KindFilterValue): void;
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

const layoutItems = [
  {
    id: "grid" as const,
    icon: "mdi-view-grid-outline",
    ariaLabel: "Grid",
    title: "Grid",
  },
  {
    id: "list" as const,
    icon: "mdi-view-list",
    ariaLabel: "List",
    title: "List",
  },
];

function setGroupBy(value: GroupByMode) {
  emit("update:groupBy", value);
}

function setLayout(value: LayoutMode) {
  emit("update:layout", value);
}

function setSearch(value: string) {
  emit("update:search", value);
}

function setKindFilter(value: KindFilterValue) {
  emit("update:kindFilter", value);
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
      :placeholder="searchPlaceholder"
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
        aria-label="Filters"
        @click="emit('click:filter')"
      />
    </RBadge>

    <RSliderBtnGroup
      v-if="smAndUp && showKindFilter && kindFilterItems.length > 0"
      :model-value="kindFilter"
      :items="kindFilterItems"
      variant="segmented"
      :aria-label="kindFilterAriaLabel"
      @update:model-value="setKindFilter"
    />

    <!-- View controls cluster — pushed right via margin-left: auto.
         At ≥ smAndUp the inline sliders carry every option; below that
         they collapse into the kebab menu so the toolbar fits on phones
         without overflowing. -->
    <div class="gallery-toolbar__controls">
      <RSliderBtnGroup
        v-if="smAndUp && showGroupBy"
        :model-value="groupByValue"
        :items="groupByItems"
        variant="segmented"
        aria-label="Group by"
        :disabled="layoutValue === 'list'"
        @update:model-value="setGroupBy"
      />

      <RSliderBtnGroup
        v-if="smAndUp"
        :model-value="layoutValue"
        :items="layoutItems"
        variant="segmented"
        aria-label="Layout"
        @update:model-value="setLayout"
      />

      <!-- Kebab mirror — only visible below smAndUp. Mirrors the slider
           state: `groupBy` items disable in list mode, same way the
           inline GroupBy slider does. -->
      <RMenu v-if="!smAndUp" location="bottom end" :offset="8" width="220px">
        <template #activator="{ props: activatorProps }">
          <RBtn
            v-bind="activatorProps"
            variant="outlined"
            surface
            icon="mdi-dots-vertical"
            rounded="circle"
            aria-label="View options"
          />
        </template>
        <template v-if="showKindFilter && kindFilterItems.length > 0">
          <RMenuItem
            v-for="item in kindFilterItems"
            :key="item.id"
            :label="item.label ?? item.title ?? item.ariaLabel ?? item.id"
            :icon="item.icon"
            :variant="kindFilter === item.id ? 'active' : 'default'"
            @click="setKindFilter(item.id)"
          />
          <RDivider />
        </template>
        <template v-if="showGroupBy && groupByItems.length > 0">
          <RMenuItem
            v-for="item in groupByItems"
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
          label="Grid"
          icon="mdi-view-grid-outline"
          :variant="layoutValue === 'grid' ? 'active' : 'default'"
          @click="setLayout('grid')"
        />
        <RMenuItem
          label="List"
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
  -webkit-backdrop-filter: blur(20px);
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
