<script setup lang="ts">
// BackgroundArt: the two-layer cross-fading backdrop. Views paint a cover
// URL via the injected `r-set-background-art` provider; we swap between
// layer A and layer B so there's always a smooth transition, never a flash.

defineOptions({ inheritAttrs: false });

defineProps<{
  layerA: string | null;
  layerB: string | null;
  activeLayer: "a" | "b";
}>();
</script>

<template>
  <div class="r-bg">
    <!-- Fallback art (no cover) comes from the CSS `background-image` on
         `.r-bg__layer` so Firefox can swap it for the static variant via
         `@-moz-document`; an inline style here would win over that override.
         A real cover URL still sets the inline background-image. -->
    <div
      class="r-bg__layer r-bg__layer--a"
      :class="{ 'r-bg__layer--active': activeLayer === 'a' }"
      :style="layerA ? { backgroundImage: `url('${layerA}')` } : {}"
    />
    <div
      class="r-bg__layer r-bg__layer--b"
      :class="{ 'r-bg__layer--active': activeLayer === 'b' }"
      :style="layerB ? { backgroundImage: `url('${layerB}')` } : {}"
    />
  </div>
  <div class="r-bg__overlay" />
</template>

<style scoped>
:deep(.r-bg__layer--a),
:deep(.r-bg__layer--b) {
  opacity: 0;
}
:deep(.r-bg__layer--active) {
  opacity: 1;
}
</style>
