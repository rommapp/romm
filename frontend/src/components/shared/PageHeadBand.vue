<script setup lang="ts">
// Owns the space above a page's header, its divider and the gap below, so
// every page puts its title and first content in the same place.
import { RDivider } from "@/lib";

defineOptions({ inheritAttrs: false });

withDefaults(
  defineProps<{
    /** What sits under the divider, which sets the space between them. */
    followedBy?: "content" | "toolbar" | "panes";
  }>(),
  { followedBy: "content" },
);

defineSlots<{
  default(): unknown;
}>();
</script>

<template>
  <div
    v-bind="$attrs"
    class="page-head-band"
    :class="`page-head-band--${followedBy}`"
  >
    <slot />
    <RDivider class="page-head-band__divider" />
  </div>
</template>

<style scoped>
/* `flow-root` keeps the header's margins inside the band. A shell that
   scrolls its own container sets the offset to clear the top bar. */
.page-head-band {
  display: flow-root;
  padding-top: calc(var(--r-page-head-band-offset, 0px) + var(--r-space-8));
}
html[data-bp~="xs"] .page-head-band {
  padding-top: calc(var(--r-page-head-band-offset, 0px) + var(--r-space-4));
}

/* Content starts 24px under the divider. A pinned toolbar's own 8px top
   padding makes up part of that; split panes meet the divider. */
.page-head-band--content .page-head-band__divider {
  margin-bottom: var(--r-space-6);
}
.page-head-band--toolbar .page-head-band__divider {
  margin-bottom: var(--r-space-4);
}
</style>
