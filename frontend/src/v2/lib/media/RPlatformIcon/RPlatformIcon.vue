<script setup lang="ts">
import { computed, ref, watch } from "vue";
import {
  DEFAULT_PLATFORM_ICON,
  shippedPlatformIconUrl,
} from "@/v2/composables/usePlatformIconCache/iconCache";
import RTooltip from "@/v2/lib/structural/RTooltip/RTooltip.vue";

defineOptions({ inheritAttrs: false });

// Platform assets are keyed by canonical slug, so `slug` is tried before the
// filesystem folder name.
//
// Hover tooltip uses RTooltip (v2 glass skin) instead of the native
// browser `title=` so the bubble matches the rest of the UI. Disable
// with `:show-tooltip="false"` if a parent surface already supplies one.

interface Props {
  /** Primary slug (platform.name in the stores). */
  name?: string;
  /** Alias for `name`. */
  slug?: string;
  /** Filesystem slug, tried only after `slug` when the two differ. */
  fsSlug?: string;
  /** Explicit override. */
  src?: string;
  size?: number | string;
  alt?: string;
  /** Tooltip text override. Falls back to `alt` then resolved slug. */
  title?: string;
  /** Show RTooltip on hover (default `true`). */
  showTooltip?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
  name: undefined,
  slug: undefined,
  fsSlug: undefined,
  src: undefined,
  size: 28,
  alt: "",
  title: undefined,
  showTooltip: true,
});

const resolvedSlug = computed(
  () => props.slug ?? props.name ?? props.fsSlug ?? "",
);
const resolvedFsSlug = computed(() => props.fsSlug ?? resolvedSlug.value);

const src = computed(
  () =>
    props.src ??
    shippedPlatformIconUrl(resolvedSlug.value.trim()) ??
    shippedPlatformIconUrl(resolvedFsSlug.value.trim()) ??
    DEFAULT_PLATFORM_ICON,
);

const resolvedSize = computed(() =>
  typeof props.size === "number" ? `${props.size}px` : props.size,
);

const tooltipText = computed(
  () => props.title ?? props.alt ?? resolvedSlug.value ?? "",
);

const failed = ref(false);
watch(src, () => {
  failed.value = false;
});

const displaySrc = computed(() =>
  failed.value ? DEFAULT_PLATFORM_ICON : src.value,
);

function onImgError() {
  if (displaySrc.value !== DEFAULT_PLATFORM_ICON) failed.value = true;
}
</script>

<template>
  <span
    v-bind="$attrs"
    class="r-platform-icon"
    :style="{ width: resolvedSize, height: resolvedSize }"
  >
    <img
      :key="displaySrc"
      :src="displaySrc"
      :alt="alt ?? resolvedSlug ?? ''"
      class="r-platform-icon__img"
      @error="onImgError"
    />
    <RTooltip
      v-if="showTooltip && tooltipText"
      :text="tooltipText"
      activator="parent"
      location="bottom"
    />
  </span>
</template>

<style scoped>
/* The `size` prop sets the wrapper dimensions directly via inline
   `width` / `height` (not a CSS var) so they survive contexts where
   the parent collapses cross-axis (e.g. `line-height: 0` flex parents
   inside RBtn). `min-width: 0` lets the wrapper still shrink inside
   flex parents that are genuinely narrower — flex items otherwise
   refuse to go below their intrinsic width. */
.r-platform-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  color: var(--r-color-fg-muted);
}

.r-platform-icon__img {
  width: 100%;
  height: 100%;
  object-fit: contain;
  image-rendering: pixelated;
}
</style>
