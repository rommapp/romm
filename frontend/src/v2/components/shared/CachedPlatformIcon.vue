<script setup lang="ts">
// Reads the blob cache from prefetchPlatformIcons. Unshipped slugs
// skip the network and use DEFAULT_PLATFORM_ICON.
import { RImg } from "@v2/lib";
import { computed, ref, watch } from "vue";
import {
  getCachedPlatformIcon,
  invalidatePlatformIcon,
} from "@/v2/composables/usePlatformIconCache";
import {
  DEFAULT_PLATFORM_ICON,
  shippedPlatformIconUrl,
} from "@/v2/composables/usePlatformIconCache/iconCache";

interface Props {
  slug: string;
  name?: string;
  size?: number;
}
const props = withDefaults(defineProps<Props>(), { name: "", size: 40 });

const cached = computed(() => getCachedPlatformIcon(props.slug));
const failed = ref(false);

watch(
  () => props.slug,
  () => {
    failed.value = false;
  },
);

const src = computed<string>(() => {
  if (failed.value || !props.slug) return DEFAULT_PLATFORM_ICON;
  return (
    cached.value ?? shippedPlatformIconUrl(props.slug) ?? DEFAULT_PLATFORM_ICON
  );
});

function onError() {
  if (cached.value) {
    invalidatePlatformIcon(props.slug);
    return;
  }
  if (src.value !== DEFAULT_PLATFORM_ICON) failed.value = true;
}
</script>

<template>
  <RImg
    :key="src"
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
