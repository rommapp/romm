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
/* Phones: plain document flow, so the page scrolls under the translucent top
   bar like Home; AppLayout's bottom padding clears the tab bar. */
.gallery-tab-shell__scroll {
  padding: 32px var(--r-row-pad) 24px;
}

.gallery-tab-shell__divider {
  margin: 0 0 24px;
}

/* Desktop: the head stays fixed and only the panel scrolls; its inset,
   cancelled by the negative margin, keeps focus rings inside the clip. */
html[data-bp~="md-and-up"] .gallery-tab-shell {
  height: calc(100vh - var(--r-nav-h));
  height: calc(100dvh - var(--r-nav-h));
  overflow: hidden;
}
html[data-bp~="md-and-up"] .gallery-tab-shell__scroll {
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow-y: auto;
  padding-bottom: 0;
}
html[data-bp~="md-and-up"] .gallery-tab-shell__panel {
  flex: 1 1 auto;
  overflow-y: auto;
  margin: -8px -8px 0;
  padding: 8px 8px var(--r-row-pad);
}
</style>
