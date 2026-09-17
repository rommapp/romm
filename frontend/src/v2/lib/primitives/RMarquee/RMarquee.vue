<script setup lang="ts">
// RMarquee — a single-line band that loops its content sideways when it is
// wider than the band and sits still when it fits. Under reduced motion the
// loop becomes a plain horizontal scroll.
import { useElementSize } from "@vueuse/core";
import { computed, ref } from "vue";
import { useReducedMotion } from "@/v2/composables/useReducedMotion";

defineOptions({ inheritAttrs: false });

interface Props {
  /** Scroll speed in pixels per second. */
  speed?: number;
  /** Space between the content and its repeat, in pixels. */
  gap?: number;
}

const props = withDefaults(defineProps<Props>(), {
  speed: 30,
  gap: 32,
});

defineSlots<{
  default(): unknown;
}>();

const bandEl = ref<HTMLElement | null>(null);
const contentEl = ref<HTMLElement | null>(null);
const { width: bandWidth } = useElementSize(bandEl);
const { width: contentWidth } = useElementSize(contentEl);
const { enabled: reducedMotion } = useReducedMotion();

const overflows = computed(() => contentWidth.value > bandWidth.value);
const moving = computed(() => overflows.value && !reducedMotion.value);

const trackStyle = computed(() => ({
  "--r-marquee-gap": `${props.gap}px`,
  "--r-marquee-duration": `${(contentWidth.value + props.gap) / props.speed}s`,
}));
</script>

<template>
  <div
    ref="bandEl"
    class="r-marquee"
    :class="{
      'r-marquee--overflow': overflows,
      'r-marquee--moving': moving,
    }"
    v-bind="$attrs"
  >
    <div class="r-marquee__track" :style="trackStyle">
      <div ref="contentEl" class="r-marquee__content">
        <slot />
      </div>
      <!-- The loop scrolls two copies by half the track, so the seam never
           shows; assistive tech reads the first copy only. -->
      <div v-if="moving" class="r-marquee__content" aria-hidden="true">
        <slot />
      </div>
    </div>
  </div>
</template>

<style scoped>
.r-marquee {
  min-width: 0;
  overflow: hidden;
}

.r-marquee--overflow {
  mask-image: linear-gradient(
    to right,
    transparent,
    black 16px,
    black calc(100% - 16px),
    transparent
  );
}

.r-marquee__track {
  display: flex;
  width: max-content;
}

.r-marquee__content {
  display: flex;
  align-items: center;
  flex-shrink: 0;
}

.r-marquee--moving .r-marquee__content {
  padding-inline-end: var(--r-marquee-gap);
}

.r-marquee--moving .r-marquee__track {
  animation: r-marquee-loop var(--r-marquee-duration) linear infinite;
}

html[data-input="mouse"] .r-marquee--moving:hover .r-marquee__track,
.r-marquee--moving:active .r-marquee__track {
  animation-play-state: paused;
}

@keyframes r-marquee-loop {
  to {
    transform: translateX(-50%);
  }
}

.r-marquee--overflow:not(.r-marquee--moving) {
  overflow-x: auto;
  scrollbar-width: none;
  mask-image: linear-gradient(to right, black calc(100% - 16px), transparent);
}

.r-marquee--overflow:not(.r-marquee--moving)::-webkit-scrollbar {
  display: none;
}
</style>
