<script setup lang="ts">
import { RTooltip } from "@v2/lib";
import { computed, ref, watch } from "vue";
import {
  DEFAULT_PLATFORM_ICON,
  platformIconUrl,
} from "@/v2/utils/platformIcons";

defineOptions({ inheritAttrs: false });

// Hover tooltip uses RTooltip (v2 glass skin) instead of the native
// browser `title=` so the bubble matches the rest of the UI. Disable
// with `:show-tooltip="false"` if a parent surface already supplies one.

interface Props {
  /** Primary slug (platform.name in the stores). */
  name?: string;
  /** Alias for `name`. */
  slug?: string;
  /** Filesystem slug, tried only when no icon ships for `slug`. */
  fsSlug?: string;
  /** Explicit override. */
  src?: string;
  size?: number | string;
  alt?: string;
  /** Tooltip text override. Falls back to `alt`. */
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

const resolvedSrc = computed(
  () => props.src || platformIconUrl(props.slug ?? props.name, props.fsSlug),
);

// A shipped file can still fail to load (e.g. a stale deploy), so an error
// drops to the default glyph once instead of showing a broken image.
const failed = ref(false);
watch(resolvedSrc, () => {
  failed.value = false;
});

const currentSrc = computed(() =>
  failed.value ? DEFAULT_PLATFORM_ICON : resolvedSrc.value,
);

function onError() {
  failed.value = true;
}

const resolvedSize = computed(() =>
  typeof props.size === "number" ? `${props.size}px` : props.size,
);

const tooltipText = computed(() => props.title || props.alt);
</script>

<template>
  <span
    v-bind="$attrs"
    class="r-platform-icon"
    :style="{ width: resolvedSize, height: resolvedSize }"
  >
    <img
      :key="currentSrc"
      :src="currentSrc"
      :alt="alt"
      class="r-platform-icon__img"
      @error="onError"
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
   inside RBtn). */
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
