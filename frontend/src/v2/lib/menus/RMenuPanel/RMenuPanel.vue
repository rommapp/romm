<script setup lang="ts">
// RMenuPanel — content container inside RMenu's slot.
//
// The v2 glass paint (background, blur, border, radius, shadow) lives
// on the parent overlay (`.r-menu` in RMenu) so RMenu and RSelect's
// dropdown share the exact same single rendering layer. RMenuPanel is
// the inner layout container: a fixed header zone (when `searchable`)
// + a body zone holding the slot content.
//
// Two layout zones:
//   • header  — only rendered when `searchable`. Holds the RMenuSearch
//     input. Stays fixed at the top so items below don't scroll behind
//     it (the body owns the overflow, not the panel).
//   • body    — slot content, gets the `padding` prop and the
//     scroll behaviour when `maxHeight` is set.
//
// When `searchable` is on, the body's `padding-top` is dropped so the
// search divider butts cleanly against the items below.
//
// `maxHeight` (optional): caps the body height. Use it for tall menus
// that may overflow the viewport on small screens. Without it the
// panel grows freely.
import { computed } from "vue";
import RMenuSearch from "../RMenuSearch/RMenuSearch.vue";

defineOptions({ inheritAttrs: false });

interface Props {
  width?: string | number;
  /** CSS max-height — when set, the body scrolls vertically. Accepts
   *  any CSS length, e.g. "320px" or "calc(100dvh - 80px)". */
  maxHeight?: string | number;
  padding?: string;
  /** Renders a built-in search input at the top of the panel. */
  searchable?: boolean;
  /** v-model:search — the current query string. */
  search?: string;
  searchPlaceholder?: string;
  searchAutoFocus?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
  width: "236px",
  maxHeight: undefined,
  padding: "6px",
  searchable: false,
  search: "",
  searchPlaceholder: "",
  searchAutoFocus: true,
});

defineEmits<{
  (e: "update:search", value: string): void;
}>();

const resolvedWidth = computed(() =>
  typeof props.width === "number" ? `${props.width}px` : props.width,
);

const resolvedMaxHeight = computed(() => {
  if (props.maxHeight === undefined) return undefined;
  return typeof props.maxHeight === "number"
    ? `${props.maxHeight}px`
    : props.maxHeight;
});
</script>

<template>
  <div
    class="r-menu-panel"
    :class="{
      'r-menu-panel--scrollable': !!resolvedMaxHeight,
      'r-menu-panel--searchable': searchable,
    }"
    :style="{ width: resolvedWidth, maxHeight: resolvedMaxHeight }"
  >
    <div v-if="searchable" class="r-menu-panel__header">
      <RMenuSearch
        :model-value="search"
        :placeholder="searchPlaceholder"
        :auto-focus="searchAutoFocus"
        @update:model-value="(v) => $emit('update:search', v)"
      />
    </div>
    <div class="r-menu-panel__body" :style="{ padding }">
      <slot />
    </div>
  </div>
</template>

<style scoped>
.r-menu-panel {
  display: flex;
  flex-direction: column;
  /* Keeps the header from spilling past the overlay's rounded
     corners when the body scrolls. */
  overflow: hidden;
}

.r-menu-panel__header {
  flex-shrink: 0;
  padding: 6px;
  border-bottom: 1px solid var(--r-color-border);
  margin-bottom: 6px;
}

.r-menu-panel__body {
  flex: 1 1 auto;
  /* Allow the body to shrink below its content height so the
     overflow rule below actually kicks in inside flex layout. */
  min-height: 0;
  display: flex;
  flex-direction: column;
}

/* Body owns the scroll, not the panel — keeps the search header
   anchored at the top while items below scroll. */
.r-menu-panel--scrollable .r-menu-panel__body {
  overflow-y: auto;
  scrollbar-width: thin;
  scrollbar-color: var(--r-color-border-strong) transparent;
}
.r-menu-panel--scrollable .r-menu-panel__body::-webkit-scrollbar {
  width: 8px;
}
.r-menu-panel--scrollable .r-menu-panel__body::-webkit-scrollbar-track {
  background: transparent;
}
.r-menu-panel--scrollable .r-menu-panel__body::-webkit-scrollbar-thumb {
  background: var(--r-color-border-strong);
  border-radius: 4px;
}
.r-menu-panel--scrollable .r-menu-panel__body::-webkit-scrollbar-thumb:hover {
  background: var(--r-color-fg-faint);
}

/* Header sits flush against the top of the panel; drop the body's
   top padding so items butt up to the header divider instead of
   sitting in a wide empty band. */
.r-menu-panel--searchable .r-menu-panel__body {
  padding-top: 0 !important;
}
</style>
