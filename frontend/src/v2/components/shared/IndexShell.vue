<script setup lang="ts">
// IndexShell: shared layout for index views (Platforms / Collections).
//
// The page scrolls as a whole, under the translucent top bar like Home, and
// the toolbar pins right below the top bar as one glass surface with it
// (usePinnedToolbar).
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
//                     Only rendered when `listMode` is true.
//   * default:       index content (grid / list / panels).
import { usePinnedToolbar } from "@/v2/composables/usePinnedToolbar";

interface Props {
  /** Enables the sticky `#listHeader` band below the toolbar. */
  listMode?: boolean;
}

withDefaults(defineProps<Props>(), { listMode: false });

defineSlots<{
  header(): unknown;
  toolbar(): unknown;
  listHeader(): unknown;
  default(): unknown;
}>();

const { toolbarHeight, pinned, bindToolbar, bindSentinel } = usePinnedToolbar();
</script>

<template>
  <section
    class="r-v2-idx-shell"
    :style="{ '--r-v2-idx-shell-toolbar-h': `${toolbarHeight}px` }"
  >
    <!-- One stable box, so the toolbar's observer sees the header grow. -->
    <div>
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
      class="r-v2-idx-shell__list-header"
      :class="{ 'r-pinned-list-header': pinned }"
    >
      <slot name="listHeader" />
    </div>

    <slot />
  </section>
</template>

<style scoped>
/* Plain document flow: <main> clears the top bar and, on phones, the bottom
   tab bar. */
.r-v2-idx-shell {
  padding: 32px var(--r-row-pad) 60px;
}
html[data-bp~="xs"] .r-v2-idx-shell {
  padding: 16px 14px 24px;
}

/* List column header: sticky just below the pinned toolbar, and under it
   (z-index 3 vs 4) so the toolbar always wins pointer events. */
.r-v2-idx-shell__list-header {
  position: sticky;
  top: calc(var(--r-nav-h) + var(--r-v2-idx-shell-toolbar-h));
  z-index: 3;
}

/* List mode: the column header and the rows run to the screen edges and keep
   the shell's gutter as padding, so only the separators and row fill move. */
.r-v2-idx-shell {
  --r-list-bleed: var(--r-row-pad);
}
.r-v2-idx-shell__list-header {
  margin-inline: calc(-1 * var(--r-list-bleed, 0px));
}
/* The header already reaches both edges by the margin above, so the pinned
   glass must not add the gutter a second time: the page has no horizontal
   clip, and the surplus on the right would scroll the document sideways. */
.r-v2-idx-shell__list-header.r-pinned-list-header::before {
  inset: 0;
}
</style>
