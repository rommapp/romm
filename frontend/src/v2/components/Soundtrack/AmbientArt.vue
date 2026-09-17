<script setup lang="ts">
// Blurred echo of a cover behind a now-playing surface. The host provides
// `position: relative`, `isolation: isolate` and `overflow: hidden`.
import { ref, watch } from "vue";
import { toCssUrl } from "@/v2/utils/css";

const props = defineProps<{ url: string }>();

// A new cover is decoded before it replaces the shown one and the two
// crossfade, so a track change never leaves the backdrop empty for a frame.
const shownUrl = ref(props.url);

watch(
  () => props.url,
  async (next) => {
    const image = new Image();
    image.src = next;
    try {
      await image.decode();
    } catch {
      // A broken cover still swaps in; the backdrop just stays empty.
    }
    if (props.url === next) shownUrl.value = next;
  },
);
</script>

<template>
  <Transition name="r-v2-ambient-art">
    <div
      :key="shownUrl"
      class="r-v2-ambient-art"
      :style="{ backgroundImage: toCssUrl(shownUrl) }"
      aria-hidden="true"
    />
  </Transition>
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

.r-v2-ambient-art-enter-active,
.r-v2-ambient-art-leave-active {
  transition: opacity var(--r-motion-slow) var(--r-motion-ease-out);
}

.r-v2-ambient-art-enter-from,
.r-v2-ambient-art-leave-to {
  opacity: 0;
}
</style>
