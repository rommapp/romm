<script setup lang="ts">
// GalleryTabShell: the non-Library tab branch of Platform / Collection. The
// head scrolls with the page; on desktop the panel reaches the viewport bottom.
import { RDivider } from "@v2/lib";

defineOptions({ inheritAttrs: false });

defineSlots<{
  head(): unknown;
  default(): unknown;
}>();
</script>

<template>
  <section v-bind="$attrs" class="gallery-tab-shell">
    <slot name="head" />
    <RDivider class="gallery-tab-shell__divider" />
    <div class="gallery-tab-shell__panel">
      <slot />
    </div>
  </section>
</template>

<style scoped>
/* Plain document flow, so the page scrolls under the translucent top bar like
   Home; AppLayout's bottom padding clears the phone tab bar. */
.gallery-tab-shell {
  padding: 32px var(--r-row-pad) 24px;
}

.gallery-tab-shell__divider {
  margin: 0 0 24px;
}

/* Desktop: fill at least the viewport so the panel, and a `fill` child such as
   the empty firmware dropzone, reaches its bottom. */
html[data-bp~="md-and-up"] .gallery-tab-shell {
  display: flex;
  flex-direction: column;
  min-height: calc(100vh - var(--r-nav-h));
  min-height: calc(100dvh - var(--r-nav-h));
  padding-bottom: var(--r-row-pad);
}
html[data-bp~="md-and-up"] .gallery-tab-shell__panel {
  flex: 1 0 auto;
  display: flex;
  flex-direction: column;
}
</style>
