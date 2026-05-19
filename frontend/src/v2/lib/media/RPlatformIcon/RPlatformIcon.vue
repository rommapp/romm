<script setup lang="ts">
import { computed, ref, watch } from "vue";
import RTooltip from "@/v2/lib/structural/RTooltip/RTooltip.vue";

defineOptions({ inheritAttrs: false });

// RPlatformIcon — renders the platform icon served from /assets/platforms
// with the same fallback chain v1 uses:
//   1. {fsSlug}.svg
//   2. {fsSlug}.ico
//   3. {slug}.svg
//   4. {slug}.ico
//   5. default.ico
//
// `fsSlug` falls back to `slug` (and `name` is still accepted as an alias
// for `slug` to stay compatible with older callers). Most entries in the
// /assets/platforms catalogue are .svg — the older `.ico`-only fallback
// was why only the handful of platforms that ship .ico (amiga, wii, …)
// were rendering.
//
// Hover tooltip uses RTooltip (v2 glass skin) instead of the native
// browser `title=` so the bubble matches the rest of the UI. Disable
// with `:show-tooltip="false"` if a parent surface already supplies one.

interface Props {
  /** Primary slug (platform.name in the stores). */
  name?: string;
  /** Alias accepted for callers using `slug`. */
  slug?: string;
  /** Filesystem slug — tried first (matches v1). */
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

// Ordered candidate URL list. We try each one in sequence; `stepIdx` walks
// through them until one loads (or we fall back to default.ico).
const candidates = computed(() => {
  if (props.src) return [props.src];
  const fs = resolvedFsSlug.value.toLowerCase().trim();
  const s = resolvedSlug.value.toLowerCase().trim();
  const out: string[] = [];
  if (fs) {
    out.push(`/assets/platforms/${fs}.svg`, `/assets/platforms/${fs}.ico`);
  }
  if (s && s !== fs) {
    out.push(`/assets/platforms/${s}.svg`, `/assets/platforms/${s}.ico`);
  }
  out.push("/assets/platforms/default.ico");
  return out;
});

const stepIdx = ref(0);
const currentSrc = computed(() => candidates.value[stepIdx.value] ?? null);

watch(candidates, () => {
  stepIdx.value = 0;
});

function onError() {
  if (stepIdx.value < candidates.value.length - 1) {
    stepIdx.value += 1;
  }
}

const resolvedSize = computed(() =>
  typeof props.size === "number" ? `${props.size}px` : props.size,
);

const tooltipText = computed(
  () => props.title ?? props.alt ?? resolvedSlug.value ?? "",
);
</script>

<template>
  <span
    v-bind="$attrs"
    class="r-platform-icon"
    :style="{ width: resolvedSize, height: resolvedSize }"
  >
    <img
      v-if="currentSrc"
      :key="currentSrc"
      :src="currentSrc"
      :alt="alt ?? resolvedSlug ?? ''"
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
