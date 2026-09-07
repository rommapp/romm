<script setup lang="ts">
// IndexShell — shared layout for index views (Platforms / Collections).
//
// Provides the same scroll architecture as GalleryShell: a section with
// `overflow: hidden` + an internal scroller, a two-layer toolbar (inflow
// + overlay), and `clip-path` on the scroller so content scrolling
// underneath the stuck toolbar is physically removed from the toolbar's
// pixel band — never leaks through the translucent surface.
//
// Why a dedicated shell instead of GalleryShell: GalleryShell is wired
// to ROM-specific stores / composables / components (`storeGalleryRoms`,
// `AlphaStrip`, `GameCard`, `FilterDrawer`, …). Index views render tiles
// of platforms or collections — different domain — so they get their
// own thin shell that owns just the scroll + sticky-toolbar machinery.
// No virtualisation (small datasets), no AlphaStrip, no selection bar.
//
// Slot contract:
//   * `#header`     — view-supplied header (PageHeader / divider / …).
//                     In the scroller's flow; scrolls away with content.
//   * `#toolbar`    — toolbar content (GalleryToolbar). Rendered TWICE —
//                     once as the inflow sticky layer, once as the
//                     absolute overlay — so it MUST be controlled (state
//                     external, props in / events out). Both renders
//                     share the same parent state via the consumer's
//                     bindings.
//   * `#listHeader` — list-mode column header (PlatformListHeader /
//                     CollectionListHeader). Only rendered when
//                     `listMode` is true. Like `#toolbar`, rendered
//                     twice (inflow sticky + absolute overlay) and
//                     covered by the extended clip-path so rows don't
//                     bleed through the translucent surface.
//   * default       — index content (grid / list / panels).
import {
  computed,
  type ComponentPublicInstance,
  onBeforeUnmount,
  ref,
} from "vue";

interface Props {
  /** Enables the sticky `#listHeader` band below the toolbar. Set when
   *  the view is in list/table mode so rows scrolling underneath the
   *  column header are clipped away. */
  listMode?: boolean;
}

withDefaults(defineProps<Props>(), { listMode: false });

defineSlots<{
  header(): unknown;
  toolbar(): unknown;
  listHeader(): unknown;
  default(): unknown;
}>();

// ── Two-layer toolbar state ─────────────────────────────────────────
// `inflowToolbarEl` is the toolbar inside the scroller. Its `offsetTop`
// is the scroll threshold beyond which the overlay takes over. The
// observed `height` drives both the clip-path inset and the spacing the
// inflow toolbar physically occupies (so the layout doesn't jump when
// the overlay activates).
const scrollerEl = ref<HTMLElement | null>(null);
const inflowToolbarEl = ref<HTMLElement | null>(null);
const toolbarHeight = ref(0);
const scrollTop = ref(0);
const inflowToolbarTop = ref(0);

let toolbarResizeObserver: ResizeObserver | null = null;

// Bound via a STABLE function ref (never an inline arrow): an inline `(el) =>
// …` ref changes identity every render, so Vue re-invokes it with `null` then
// the element on every re-render, resetting the measurements mid-scroll.
function bindInflowToolbarEl(el: Element | ComponentPublicInstance | null) {
  const node = (el as HTMLElement | null) ?? null;
  toolbarResizeObserver?.disconnect();
  toolbarResizeObserver = null;
  inflowToolbarEl.value = node;
  if (!node) {
    toolbarHeight.value = 0;
    inflowToolbarTop.value = 0;
    return;
  }
  const measure = () => {
    toolbarHeight.value = node.getBoundingClientRect().height;
    inflowToolbarTop.value = node.offsetTop;
  };
  measure();
  toolbarResizeObserver = new ResizeObserver(measure);
  toolbarResizeObserver.observe(node);
}

function onScroll(e: Event) {
  scrollTop.value = (e.target as HTMLElement).scrollTop;
}

// `isStuck` flips to true the moment the inflow toolbar's top edge
// reaches the scroller's visible top. At that moment the overlay becomes
// visible and the scroller's top band is clipped, so any content
// scrolling up never reaches the overlay's pixel area.
const isStuck = computed(() => {
  const threshold = inflowToolbarTop.value;
  if (threshold <= 0) return scrollTop.value > 0;
  return scrollTop.value >= threshold;
});

onBeforeUnmount(() => {
  toolbarResizeObserver?.disconnect();
  toolbarResizeObserver = null;
});
</script>

<template>
  <section
    class="r-v2-idx-shell"
    :class="{
      'r-v2-idx-shell--stuck': isStuck,
      'r-v2-idx-shell--list': listMode,
    }"
    :style="{ '--r-v2-idx-shell-toolbar-h': `${toolbarHeight}px` }"
  >
    <div
      ref="scrollerEl"
      class="r-v2-idx-shell__scroller r-v2-scroll-hidden"
      @scroll="onScroll"
    >
      <div class="r-v2-idx-shell__header">
        <slot name="header" />
      </div>

      <div
        :ref="bindInflowToolbarEl"
        class="r-v2-idx-shell__toolbar r-v2-idx-shell__toolbar--inflow"
      >
        <slot name="toolbar" />
      </div>

      <!-- Inflow list header — sticky below the toolbar in list mode.
           Shares the band that the extended clip-path covers when
           stuck, so it's visually hidden once the overlay twin (below)
           takes over. -->
      <div v-if="listMode" class="r-v2-idx-shell__list-header">
        <slot name="listHeader" />
      </div>

      <div class="r-v2-idx-shell__content">
        <slot />
      </div>
    </div>

    <!-- Toolbar overlay — absolute against the section, OUTSIDE the
         scroller. Transparent so the BackgroundArt shows through; the
         scroller's clip strips content from this band when stuck, so
         the overlay reveals only what's behind the section, never the
         content underneath. -->
    <div
      v-show="isStuck"
      class="r-v2-idx-shell__toolbar r-v2-idx-shell__toolbar--overlay"
    >
      <slot name="toolbar" />
    </div>

    <!-- List header overlay — twin of the inflow list header. Mirrors
         the toolbar overlay pattern: absolute against the section,
         outside the clipped scroller. Together with the extended
         clip-path, rows scrolling underneath are physically removed
         from this pixel band — no see-through through the translucent
         column header. -->
    <div
      v-if="listMode"
      v-show="isStuck"
      class="r-v2-idx-shell__list-header-overlay"
    >
      <slot name="listHeader" />
    </div>
  </section>
</template>

<style scoped>
.r-v2-idx-shell {
  display: flex;
  flex-direction: column;
  overflow: hidden;
  /* Viewport-relative height — same rationale as GalleryShell: percentage
     heights on descendants of flex-computed boxes don't always resolve,
     and when they fail the inner scroller becomes content-sized and stops
     overflowing. Subtracting the navbar bypasses that. `dvh` (not `vh`)
     matches the mobile visible viewport so the section doesn't spill below
     the fold and force a second, document-level scroll. */
  height: calc(100vh - var(--r-nav-h));
  height: calc(100dvh - var(--r-nav-h));
  position: relative;
}

/* On sm-and-down the section keeps its full `100dvh - nav` height so tiles
   scroll UNDER the translucent bottom tab bar. The layout <main> adds a
   bottom padding for the bar (flow views need it); cancel it here with a
   matching negative margin so this full-height section doesn't push the
   document past one viewport (a second, global scroll on top of the internal
   one). The scroller's bottom padding lifts the last row clear of the bar. */
html[data-bp~="sm-and-down"] .r-v2-idx-shell {
  margin-bottom: calc(
    -1 * (var(--r-bottom-nav-h) + env(safe-area-inset-bottom))
  );
}

.r-v2-idx-shell__scroller {
  flex: 1;
  height: 100%;
  overflow-y: auto;
  padding: 0 var(--r-row-pad) 60px;
}

.r-v2-idx-shell__header {
  padding-top: 32px;
}

/* Toolbar — both layers share the same internal styling. Transparent
   by default; the BackgroundArt behind the section shows through.
   `padding-bottom` reserves breathing space between the toolbar UI and
   the first row of content below. */
.r-v2-idx-shell__toolbar {
  padding-bottom: 16px;
}

/* Inflow layer — sticky at the top of the scroller. The compositor
   pins it smoothly as the user scrolls past the header. The scroller's
   clip-path hides this layer once `--stuck` is true; the overlay then
   takes over visually. */
.r-v2-idx-shell__toolbar--inflow {
  position: sticky;
  top: 0;
  z-index: 4;
}

/* Overlay layer — absolute against the section, mirrors the scroller's
   column so columns align with the inflow. z-index above the inflow
   so when both paint at y=0 (transition frame), the overlay stacks
   cleanly on top. */
.r-v2-idx-shell__toolbar--overlay {
  position: absolute;
  top: 0;
  left: var(--r-row-pad);
  right: var(--r-row-pad);
  z-index: 5;
}

/* List column header — sticky just below the toolbar. `top` matches
   the toolbar's pinned height so when both are stuck they stack
   cleanly; z-index 3 keeps it under the inflow toolbar (4) so the
   toolbar always wins pointer events when both paint at the same y. */
.r-v2-idx-shell__list-header {
  position: sticky;
  top: var(--r-v2-idx-shell-toolbar-h, 64px);
  z-index: 3;
}

/* List header overlay — absolute, mirrors the scroller's column.
   z-index 4 keeps it under the toolbar overlay (5) but above any
   in-flow content peeking through. */
.r-v2-idx-shell__list-header-overlay {
  position: absolute;
  top: var(--r-v2-idx-shell-toolbar-h, 64px);
  left: var(--r-row-pad);
  right: var(--r-row-pad);
  z-index: 4;
}

/* While stuck, clip the scroller's top toolbar-band so content
   scrolling underneath the overlay is physically removed from that
   pixel area. The transparent overlay then reveals only the section's
   background (BackgroundArt blur) — never the content.

   In list mode, extend the clip to also cover the list-header band
   below the toolbar so rows don't bleed through the (translucent)
   sticky column header. */
.r-v2-idx-shell--stuck .r-v2-idx-shell__scroller {
  clip-path: inset(var(--r-v2-idx-shell-toolbar-h, 64px) 0 0 0);
}
.r-v2-idx-shell--stuck.r-v2-idx-shell--list .r-v2-idx-shell__scroller {
  clip-path: inset(
    calc(var(--r-v2-idx-shell-toolbar-h, 64px) + var(--r-list-header-h)) 0 0 0
  );
}

html[data-bp~="xs"] .r-v2-idx-shell__scroller {
  /* Last row clears the bottom tab bar (content still scrolls under its
     glass); the section extends under the bar, so the padding does the lift. */
  padding: 0 14px
    calc(var(--r-bottom-nav-h) + env(safe-area-inset-bottom) + 24px);
}
html[data-bp~="xs"] .r-v2-idx-shell__header {
  padding-top: 16px;
}
</style>
