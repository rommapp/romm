<script setup lang="ts">
// IndexShell — shared layout for index views (Platforms / Collections).
//
// Provides the same scroll architecture as GalleryShell: a section running
// under the top bar with an internal scroller, and a sticky toolbar that pins
// right below the top bar as one glass surface with it (usePinnedToolbar).
//
// Why a dedicated shell instead of GalleryShell: GalleryShell is wired
// to ROM-specific stores / composables / components (`storeGalleryRoms`,
// `AlphaStrip`, `GameCard`, `FilterDrawer`, …). Index views render tiles
// of platforms or collections — different domain — so they get their
// own thin shell that owns just the scroll + sticky-toolbar machinery.
// No virtualisation (small datasets), no AlphaStrip, no selection bar.
//
// Slot contract:
//   * `#header`:     view-supplied header (PageHeader / divider / …).
//                     In the scroller's flow; scrolls away with content.
//   * `#toolbar`:    toolbar content (GalleryToolbar), pinned under the
//                     top bar.
//   * `#listHeader`: list-mode column header (PlatformListHeader /
//                     CollectionListHeader), sticky below the toolbar.
//                     Only rendered when `listMode` is true.
//   * default:       index content (grid / list / panels).
import { ref } from "vue";
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

const scrollTop = ref(0);
const { toolbarHeight, pinned, bindToolbar, bindSentinel } =
  usePinnedToolbar(scrollTop);

function onScroll(e: Event) {
  scrollTop.value = (e.target as HTMLElement).scrollTop;
}
</script>

<template>
  <section
    class="r-v2-idx-shell"
    :style="{ '--r-v2-idx-shell-toolbar-h': `${toolbarHeight}px` }"
  >
    <div class="r-v2-idx-shell__scroller r-v2-scroll-hidden" @scroll="onScroll">
      <div class="r-v2-idx-shell__header">
        <slot name="header" />
      </div>

      <div
        :ref="bindSentinel"
        class="r-v2-idx-shell__pin-sentinel"
        aria-hidden="true"
      />
      <div
        :ref="bindToolbar"
        class="r-pinned-toolbar"
        :class="{ 'r-pinned-toolbar--pinned': pinned }"
      >
        <slot name="toolbar" />
      </div>

      <div v-if="listMode" class="r-v2-idx-shell__list-header">
        <slot name="listHeader" />
      </div>

      <div class="r-v2-idx-shell__content">
        <slot />
      </div>
    </div>
  </section>
</template>

<style scoped>
.r-v2-idx-shell {
  display: flex;
  flex-direction: column;
  overflow: hidden;
  /* Viewport-relative height — same rationale as GalleryShell: percentage
     heights on descendants of flex-computed boxes don't always resolve, and
     when they fail the inner scroller stops overflowing. `dvh` (not `vh`)
     matches the mobile visible viewport so the section doesn't spill below
     the fold and force a second, document-level scroll. */
  height: 100vh;
  height: 100dvh;
  /* Run up under the fixed top bar (<main> reserves its height with a top
     padding) so content scrolls behind its glass. */
  margin-top: calc(-1 * var(--r-nav-h));
  position: relative;
}

/* On sm-and-down the section also runs under the bottom tab bar: cancel
   <main>'s bottom padding for it so the document stays one viewport tall. */
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

/* The header clears the top bar the section runs under. Not the scroller's
   padding: that would also offset the sticky toolbar. */
.r-v2-idx-shell__header {
  padding-top: calc(var(--r-nav-h) + 32px);
}

/* Zero-height marker at the toolbar's natural top (see usePinnedToolbar). */
.r-v2-idx-shell__pin-sentinel {
  height: 0;
}

/* List column header: sticky just below the pinned toolbar, and under it
   (z-index 3 vs 4) so the toolbar always wins pointer events. */
.r-v2-idx-shell__list-header {
  position: sticky;
  top: calc(var(--r-nav-h) + var(--r-v2-idx-shell-toolbar-h, 64px));
  z-index: 3;
}

html[data-bp~="xs"] .r-v2-idx-shell__scroller {
  /* Last row clears the bottom tab bar (content still scrolls under its
     glass); the section extends under the bar, so the padding does the lift. */
  padding: 0 14px
    calc(var(--r-bottom-nav-h) + env(safe-area-inset-bottom) + 24px);
}
html[data-bp~="xs"] .r-v2-idx-shell__header {
  padding-top: calc(var(--r-nav-h) + 16px);
}
</style>
