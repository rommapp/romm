<script setup lang="ts">
// CachedPlatformIcon — reads the platform icon from the in-memory
// blob cache populated by `prefetchPlatformIcons(...)`. When the
// cache has a hit, renders a plain `<img>` with the blob URL (zero
// network).
//
// Self-contained fallback chain: cached blob → /assets/platforms/
// {slug}.svg → .ico → default.ico → a clean RIcon glyph. Bypasses
// the v1 PlatformIcon component intentionally so the terminal
// fallback is a styled Material icon rather than the browser's
// broken-image glyph (which is what the user saw before).
import { RIcon } from "@v2/lib";
import {
  getCachedPlatformIcon,
  invalidatePlatformIcon,
} from "@/v2/composables/usePlatformIconCache";
import { computed, ref, watch } from "vue";

interface Props {
  slug: string;
  name?: string;
  size?: number;
}
const props = withDefaults(defineProps<Props>(), { name: "", size: 40 });

const cached = computed(() => getCachedPlatformIcon(props.slug));

// 0 = try cached blob, 1 = .svg, 2 = .ico, 3 = default.ico,
// 4+ = give up and render the Material icon fallback.
const step = ref(0);

watch(
  () => props.slug,
  () => {
    step.value = 0;
  },
);

const src = computed<string | undefined>(() => {
  const slug = props.slug.toLowerCase();
  if (step.value === 0) return cached.value ?? undefined;
  if (step.value === 1) return `/assets/platforms/${slug}.svg`;
  if (step.value === 2) return `/assets/platforms/${slug}.ico`;
  if (step.value === 3) return `/assets/platforms/default.ico`;
  return undefined;
});

const exhausted = computed(() => step.value >= 4);

function onError() {
  // The cached blob failed to decode — drop it so the reactive
  // re-render advances cleanly through the rest of the chain
  // (and any other consumer of the same slug stops getting it).
  if (step.value === 0 && cached.value) invalidatePlatformIcon(props.slug);
  step.value += 1;
}
</script>

<template>
  <img
    v-if="!exhausted && src"
    :src="src"
    :alt="name || slug"
    :title="name || slug"
    :width="size"
    :height="size"
    class="r-v2-cached-platform-icon"
    @error="onError"
  />
  <RIcon
    v-else
    icon="mdi-gamepad-variant-outline"
    :size="Number(size)"
    class="r-v2-cached-platform-icon__fallback"
    :title="name || slug"
  />
</template>

<style scoped>
.r-v2-cached-platform-icon {
  object-fit: contain;
  display: block;
  flex-shrink: 0;
}
.r-v2-cached-platform-icon__fallback {
  color: var(--r-color-fg-muted);
  flex-shrink: 0;
}
</style>
