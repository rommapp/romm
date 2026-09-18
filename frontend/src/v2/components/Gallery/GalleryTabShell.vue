<script setup lang="ts">
// GalleryTabShell: the non-Library tab branch of Platform / Collection. On
// desktop the head stays fixed and only the panel scrolls; phones scroll the page.
import { RDivider } from "@v2/lib";

defineOptions({ inheritAttrs: false });

defineProps<{
  /** Remounts the panel when it changes, so each tab opens at the top. */
  panelKey?: string;
}>();

defineSlots<{
  head(): unknown;
  default(): unknown;
}>();
</script>

<template>
  <section v-bind="$attrs" class="gallery-tab-shell">
    <div class="gallery-tab-shell__scroll">
      <slot name="head" />
      <RDivider class="gallery-tab-shell__divider" />
      <div :key="panelKey" class="gallery-tab-shell__panel">
        <slot />
      </div>
    </div>
  </section>
</template>

<style scoped>
.gallery-tab-shell {
  /* `dvh` so the section matches the mobile visible viewport instead of
     stacking a document scroll on the inner one (as GalleryShell does). */
  height: calc(100vh - var(--r-nav-h));
  height: calc(100dvh - var(--r-nav-h));
  overflow: hidden;
  position: relative;
}
/* <main> reserves the bottom tab bar on phones; run under the translucent bar
   instead, the scroll's bottom spacer lifts the last content clear of it. */
html[data-bp~="sm-and-down"] .gallery-tab-shell {
  margin-bottom: calc(
    -1 * (var(--r-bottom-nav-h) + env(safe-area-inset-bottom))
  );
}

.gallery-tab-shell__scroll {
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow-y: auto;
  padding: 32px var(--r-row-pad) 0;
}
html[data-bp~="sm-and-down"] .gallery-tab-shell__scroll {
  padding-bottom: calc(
    var(--r-bottom-nav-h) + env(safe-area-inset-bottom) + 24px
  );
}

.gallery-tab-shell__divider {
  margin: 0 0 24px;
}

/* Desktop: the panel takes the rest of the height and scrolls on its own. The
   inset (cancelled by the negative margin) keeps focus rings inside its clip. */
html[data-bp~="md-and-up"] .gallery-tab-shell__panel {
  flex: 1 1 auto;
  overflow-y: auto;
  margin: -8px -8px 0;
  padding: 8px 8px var(--r-row-pad);
}
</style>
