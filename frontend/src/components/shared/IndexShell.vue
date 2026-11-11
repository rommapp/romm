<script setup lang="ts">
// IndexShell: shared layout for index views (Platforms / Collections).
//
// Content scrolls in an inner container of a ViewportShell, under the
// translucent top bar, and the toolbar pins right below the top bar as one
// glass surface with it (usePinnedToolbar).
//
// Why a dedicated shell instead of GalleryShell: GalleryShell is wired
// to ROM-specific stores / composables / components (`storeGalleryRoms`,
// `AlphaStrip`, `GameCard`, `FilterDrawer`, …). Index views render tiles
// of platforms or collections, a different domain, so they get their
// own thin shell that owns just the sticky-toolbar machinery.
// No virtualisation (small datasets), no AlphaStrip, no selection bar.
//
// Slot contract:
//   * `#header`:     view-supplied header (PageHeader / divider / …).
//                     Scrolls away with content.
//   * `#toolbar`:    toolbar content (GalleryToolbar), pinned under the
//                     top bar.
//   * `#listHeader`: list-mode column header (PlatformListHeader /
//                     CollectionListHeader), sticky below the toolbar.
//   * `#listRows`:   list-mode rows, in one table with the header.
//                     Both list slots render only when `listMode` is true.
//   * default:       index content (grid / panels / loading and empty states).
import { useScroll } from "@vueuse/core";
import { ref } from "vue";
import ViewportShell from "@/components/shared/ViewportShell.vue";
import { useBreakpoint } from "@/composables/useBreakpoint";
import { usePinnedToolbar } from "@/composables/usePinnedToolbar";

interface Props {
  /** Enables the list header and rows. */
  listMode?: boolean;
  /** Names the list's table. */
  listLabel?: string | undefined;
}

withDefaults(defineProps<Props>(), { listMode: false, listLabel: undefined });

defineSlots<{
  header(): unknown;
  toolbar(): unknown;
  listHeader(): unknown;
  listRows(): unknown;
  default(): unknown;
}>();

const scrollerEl = ref<HTMLElement | null>(null);
const { y: scrollTop } = useScroll(scrollerEl);
const { toolbarHeight, pinned, bindToolbar, bindSentinel } =
  usePinnedToolbar(scrollTop);
// Phones and tablets get a sort menu and plain link rows, so no table.
const { smAndDown } = useBreakpoint();
</script>

<template>
  <ViewportShell
    :scroller="scrollerEl"
    class="r-idx-shell"
    :style="{ '--r-idx-shell-toolbar-h': `${toolbarHeight}px` }"
  >
    <div ref="scrollerEl" class="r-idx-shell__scroller" tabindex="-1">
      <!-- One stable box, so the toolbar's observer sees the header grow. -->
      <div class="r-idx-shell__header">
        <slot name="header" />
      </div>

      <div :ref="bindSentinel" aria-hidden="true" />
      <div
        :ref="bindToolbar"
        class="r-pinned-toolbar"
        :class="{ 'r-pinned-toolbar--pinned': pinned }"
      >
        <slot name="toolbar" />
      </div>

      <div
        v-if="listMode"
        :role="smAndDown ? undefined : 'table'"
        :aria-label="smAndDown ? undefined : listLabel"
      >
        <div
          class="r-idx-shell__list-header"
          :class="{ 'r-pinned-list-header': pinned }"
        >
          <slot name="listHeader" />
        </div>
        <slot name="listRows" />
      </div>

      <slot />
    </div>
  </ViewportShell>
</template>

<style scoped>
/* Positioned so the sentinel's offsetTop is measured from the scroller. */
.r-idx-shell__scroller {
  flex: 1;
  height: 100%;
  position: relative;
  overflow-y: auto;
  outline: none;
  padding: 0 var(--r-gutter-r) 60px var(--r-gutter-l);
}
html[data-bp~="sm-and-down"] .r-idx-shell__scroller {
  padding-bottom: calc(60px + var(--r-bottom-nav-h) + var(--r-safe-b));
}
html[data-bp~="xs"] .r-idx-shell__scroller {
  padding-bottom: calc(24px + var(--r-bottom-nav-h) + var(--r-safe-b));
}

/* Clears the top bar here rather than on the scroller, whose padding would
   also offset the sticky toolbar. */
.r-idx-shell__header {
  padding-top: calc(var(--r-nav-h) + 32px);
}
html[data-bp~="xs"] .r-idx-shell__header {
  padding-top: calc(var(--r-nav-h) + 16px);
}

/* List column header: sticky just below the pinned toolbar, and under it
   (z-index 3 vs 4) so the toolbar always wins pointer events. */
.r-idx-shell__list-header {
  position: sticky;
  top: calc(var(--r-nav-h) + var(--r-idx-shell-toolbar-h));
  z-index: 3;
}

/* Tiles scrolled into view by keyboard or pad nav land clear of the fixed bars. */
.r-idx-shell :deep([data-focus-key]) {
  scroll-margin-top: calc(var(--r-nav-h) + var(--r-idx-shell-toolbar-h));
  scroll-margin-bottom: calc(var(--r-bottom-nav-h) + var(--r-safe-b));
}

/* List mode: the column header and the rows run to the screen edges and keep
   the shell's gutter as padding, so only the separators and row fill move. */
.r-idx-shell {
  --r-list-bleed: var(--r-row-pad);
}
.r-idx-shell__list-header {
  margin-inline: calc(-1 * var(--r-list-bleed, 0px));
}
/* The margin above already spans the gutter, so the glass adds only the shell's
   safe-area padding; more would scroll the unclipped page sideways. */
.r-idx-shell__list-header.r-pinned-list-header::before {
  inset: 0 calc(-1 * var(--r-safe-r)) 0 calc(-1 * var(--r-safe-l));
}
</style>
