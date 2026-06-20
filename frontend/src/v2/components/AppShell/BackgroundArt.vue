<script setup lang="ts">
// BackgroundArt — the two-layer cross-fading backdrop. Views paint a cover
// URL via the injected `r-v2-set-background-art` provider; we swap between
// layer A and layer B so there's always a smooth transition, never a flash.

defineOptions({ inheritAttrs: false });

defineProps<{
  layerA: string | null;
  layerB: string | null;
  activeLayer: "a" | "b";
}>();
</script>

<template>
  <div class="r-v2-bg">
    <div
      class="r-v2-bg__layer r-v2-bg__layer--a"
      :class="{ 'r-v2-bg__layer--active': activeLayer === 'a' }"
      :style="
        layerA
          ? { backgroundImage: `url('${layerA}')` }
          : { backgroundImage: `url('/assets/auth_background.svg')` }
      "
    />
    <div
      class="r-v2-bg__layer r-v2-bg__layer--b"
      :class="{ 'r-v2-bg__layer--active': activeLayer === 'b' }"
      :style="
        layerB
          ? { backgroundImage: `url('${layerB}')` }
          : { backgroundImage: `url('/assets/auth_background.svg')` }
      "
    />
  </div>
  <div class="r-v2-bg__overlay" />
</template>

<style scoped>
:deep(.r-v2-bg__layer--a),
:deep(.r-v2-bg__layer--b) {
  opacity: 0;
}
:deep(.r-v2-bg__layer--active) {
  opacity: 1;
}
</style>
