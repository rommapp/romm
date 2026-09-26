<script setup lang="ts">
// CachedPlatformIcon — reads the platform icon from the in-memory
// blob cache populated by `prefetchPlatformIcons(...)`. When the
// cache has a hit, renders a plain `<img>` with the blob URL (zero
// network). Otherwise it uses the shipped icon, or `default.ico` when
// none ships, so users never see the browser's broken-image glyph.
import { RImg } from "@v2/lib";
import { computed, ref, watch } from "vue";
import {
  getCachedPlatformIcon,
  invalidatePlatformIcon,
} from "@/v2/composables/usePlatformIconCache";
import {
  DEFAULT_PLATFORM_ICON,
  platformIconUrl,
} from "@/v2/utils/platformIcons";

interface Props {
  slug: string;
  name?: string;
  size?: number;
}
const props = withDefaults(defineProps<Props>(), { name: "", size: 40 });

// Callers sometimes hand us an undefined slug (e.g. VSelect's `#selection`
// slot while the model value matches no item).
const cached = computed(() =>
  props.slug ? getCachedPlatformIcon(props.slug) : undefined,
);
const failed = ref(false);

watch(
  () => props.slug,
  () => {
    failed.value = false;
  },
);

const src = computed<string>(() => {
  if (failed.value) return DEFAULT_PLATFORM_ICON;
  return cached.value ?? platformIconUrl(props.slug);
});

function onError() {
  // A blob that fails to decode is dropped so the shipped URL gets a turn.
  if (cached.value) invalidatePlatformIcon(props.slug);
  else failed.value = true;
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
