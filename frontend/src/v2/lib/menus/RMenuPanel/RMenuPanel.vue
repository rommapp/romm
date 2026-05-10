<script setup lang="ts">
// RMenuPanel — content container inside RMenu's slot.
//
// The v2 glass paint (background, blur, border, radius, shadow) lives
// on the parent overlay (`.r-menu` in RMenu) so RMenu and RSelect's
// dropdown share the exact same single rendering layer. RMenuPanel is
// the inner layout container: width + padding + flex column for
// header / items / dividers. Painting it again here would compound
// the backdrop-filter blur and shift the perceived colour vs. RSelect.
//
// `maxHeight` (optional): caps the panel height and lets the inner
// list scroll. Use it for tall menus that may overflow the viewport
// on small screens (UserMenu, long platform pickers…). Without it the
// panel grows freely and may be clipped off-screen.

defineOptions({ inheritAttrs: false });

interface Props {
  width?: string | number;
  /** CSS max-height — when set, the panel scrolls vertically. Accepts
   *  any CSS length, e.g. "320px" or "calc(100dvh - 80px)". */
  maxHeight?: string | number;
  padding?: string;
}

const props = withDefaults(defineProps<Props>(), {
  width: "236px",
  maxHeight: undefined,
  padding: "6px",
});

const resolvedWidth =
  typeof props.width === "number" ? `${props.width}px` : props.width;

const resolvedMaxHeight =
  props.maxHeight === undefined
    ? undefined
    : typeof props.maxHeight === "number"
      ? `${props.maxHeight}px`
      : props.maxHeight;
</script>

<template>
  <div
    class="r-menu-panel"
    :class="{ 'r-menu-panel--scrollable': !!resolvedMaxHeight }"
    :style="{
      width: resolvedWidth,
      maxHeight: resolvedMaxHeight,
      padding,
    }"
  >
    <slot />
  </div>
</template>

<style scoped>
.r-menu-panel {
  display: flex;
  flex-direction: column;
}

/* Scrollable variant — used when maxHeight is set so tall menus stay
   reachable on small viewports without spilling off-screen. */
.r-menu-panel--scrollable {
  overflow-y: auto;
  /* Slim, theme-aware scrollbar so it reads as the glass surface
     instead of the OS default. */
  scrollbar-width: thin;
  scrollbar-color: var(--r-color-border-strong) transparent;
}
.r-menu-panel--scrollable::-webkit-scrollbar {
  width: 8px;
}
.r-menu-panel--scrollable::-webkit-scrollbar-track {
  background: transparent;
}
.r-menu-panel--scrollable::-webkit-scrollbar-thumb {
  background: var(--r-color-border-strong);
  border-radius: 4px;
}
.r-menu-panel--scrollable::-webkit-scrollbar-thumb:hover {
  background: var(--r-color-fg-faint);
}
</style>
