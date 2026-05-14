<script setup lang="ts">
// CachedPlatformIcon — reads the platform icon from the in-memory
// blob cache populated by `prefetchPlatformIcons(...)`. When the
// cache has a hit, renders a plain `<img>` with the blob URL (zero
// network).
//
// Self-contained fallback chain, mirroring v1's PlatformIcon:
//   cached blob → /assets/platforms/{slug}.svg → .ico → default.ico
// The terminal step is always `default.ico` (the same bundled glyph
// every other platform-icon surface in the app falls back to), so
// users never see the browser's broken-image icon or a Material icon
// pretending to be a platform.
import { RImg } from "@v2/lib";
import { computed, ref, watch } from "vue";
import {
  getCachedPlatformIcon,
  invalidatePlatformIcon,
} from "@/v2/composables/usePlatformIconCache";

interface Props {
  slug: string;
  name?: string;
  size?: number;
}
const props = withDefaults(defineProps<Props>(), { name: "", size: 40 });

const cached = computed(() => getCachedPlatformIcon(props.slug));

// 0 = try cached blob first, then the canonical .svg
// 1 = .ico fallback
// 2 = terminal default.ico — we stop advancing here so the browser
//     never paints its broken-image glyph in the unlikely case the
//     bundled fallback itself can't be loaded.
const step = ref(0);

watch(
  () => props.slug,
  () => {
    step.value = 0;
  },
);

const src = computed<string>(() => {
  // Defensive: callers sometimes hand us `undefined` (e.g. VSelect's
  // `#selection` slot rendering a model value that doesn't match any
  // item, or a parent passing a transient empty slug while it
  // hydrates). Skip straight to the terminal fallback rather than
  // crashing on `.toLowerCase()`.
  if (!props.slug) return "/assets/platforms/default.ico";
  const slug = props.slug.toLowerCase();
  if (step.value === 0) {
    return cached.value ?? `/assets/platforms/${slug}.svg`;
  }
  if (step.value === 1) return `/assets/platforms/${slug}.ico`;
  return "/assets/platforms/default.ico";
});

function onError() {
  // The cached blob failed to decode — drop it so the reactive
  // re-render advances cleanly through the rest of the chain.
  if (step.value === 0 && cached.value) invalidatePlatformIcon(props.slug);
  if (step.value < 2) step.value += 1;
}
</script>

<template>
  <RImg
    :src="src"
    :alt="name || slug"
    :title="name || slug"
    :width="size"
    :height="size"
    contain
    class="r-v2-cached-platform-icon"
    @error="onError"
  />
</template>

<style scoped>
.r-v2-cached-platform-icon {
  object-fit: contain;
  display: block;
  flex-shrink: 0;
}
</style>
