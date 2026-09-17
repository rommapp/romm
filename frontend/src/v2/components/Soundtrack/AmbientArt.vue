<script setup lang="ts">
// Blurred echo of a cover behind a now-playing surface. The host provides
// `position: relative`, `isolation: isolate` and `overflow: hidden`.
import { toCssUrl } from "@/v2/utils/css";

defineProps<{ url: string }>();
</script>

<template>
  <div
    class="r-v2-ambient-art"
    :style="{ backgroundImage: toCssUrl(url) }"
    aria-hidden="true"
  />
</template>

<style scoped>
/* Scaled past the edges so the blur never shows a hard boundary; masked so
   it fades out towards the bottom. */
.r-v2-ambient-art {
  position: absolute;
  inset: 0;
  z-index: -1;
  background-size: cover;
  background-position: center 30%;
  transform: scale(1.3);
  filter: blur(72px) saturate(1.4);
  opacity: 0.2;
  mask-image: linear-gradient(to bottom, black 0%, transparent 85%);
  pointer-events: none;
}
</style>
