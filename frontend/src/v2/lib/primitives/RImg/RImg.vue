<script setup lang="ts">
// RImg — wraps a native <img> with three slot-driven
// states: `loading` (while the network fetch is in flight), `error`
// (when load fails or src is empty), and `default` (a content overlay
// rendered on top of the loaded image — captions, hover CTAs, etc).
//
// Layout model — the wrapper takes the explicit width/height, the
// `<img>` fills it. Without `cover`/`contain` the image scales by
// width (height auto from natural aspect ratio) — matches the v2 logo
// usage in AppNav / AuthCard / OIDCButton. Add `cover` (fill + crop)
// or `contain` (fit inside, letterbox) when the wrapper has both
// width AND height set and you want object-fit behaviour.
//
// `aspectRatio` accepts CSS-native syntax (`"16/9"` or numeric `1.78`)
// — applied to the wrapper. Pair with `width` to get a fixed-ratio
// container that flexes with its parent's width.
//
// Fades in once loaded so the swap from placeholder → image doesn't
// pop. Matches the motion vocabulary RSwitch / RIcon established.
import { computed, ref, useSlots, watch } from "vue";

defineOptions({ inheritAttrs: false });

interface Props {
  src?: string;
  alt?: string;
  width?: string | number;
  height?: string | number;
  /** Fill the wrapper, crop overflow (object-fit: cover). */
  cover?: boolean;
  /** Fit inside the wrapper, letterbox (object-fit: contain). */
  contain?: boolean;
  /** CSS aspect-ratio on the wrapper. `"16/9"`, `"1/1"`, `1.78`. */
  aspectRatio?: string | number;
}

const props = withDefaults(defineProps<Props>(), {
  src: undefined,
  alt: undefined,
  width: undefined,
  height: undefined,
  cover: false,
  contain: false,
  aspectRatio: undefined,
});

const emit = defineEmits<{
  (e: "load"): void;
  (e: "error"): void;
}>();

const slots = useSlots();

type LoadState = "loading" | "loaded" | "error";
// Start in `loading` regardless of `src` — "no src yet" is a waiting
// state (e.g. consumer is hydrating an async value), not an error.
// `error` only flips after a failed network attempt.
const state = ref<LoadState>("loading");

// Reset to `loading` whenever src changes so a swap re-enters the
// loading fade rather than flashing the previous image.
watch(
  () => props.src,
  () => {
    state.value = "loading";
  },
);

function onLoad() {
  state.value = "loaded";
  emit("load");
}
function onError() {
  state.value = "error";
  emit("error");
}

// Length resolver — bare numbers / numeric strings → px, anything else
// (`"100%"`, `"24em"`, `"clamp(...)"`) passes through.
function toLength(v: string | number | undefined): string | undefined {
  if (v === undefined || v === null || v === "") return undefined;
  if (typeof v === "number") return `${v}px`;
  if (/^\d+(\.\d+)?$/.test(v)) return `${v}px`;
  return v;
}

const wrapperStyle = computed(() => ({
  width: toLength(props.width),
  height: toLength(props.height),
  aspectRatio:
    props.aspectRatio !== undefined ? String(props.aspectRatio) : undefined,
}));
</script>

<template>
  <div
    v-bind="$attrs"
    class="r-img"
    :class="{
      'r-img--loading': state === 'loading',
      'r-img--loaded': state === 'loaded',
      'r-img--error': state === 'error',
      'r-img--cover': cover,
      'r-img--contain': contain,
    }"
    :style="wrapperStyle"
  >
    <img
      v-if="src && state !== 'error'"
      :src="src"
      :alt="alt ?? ''"
      class="r-img__image"
      decoding="async"
      @load="onLoad"
      @error="onError"
    />

    <div v-if="state === 'loading' && slots.loading" class="r-img__layer">
      <slot name="loading" />
    </div>
    <div
      v-else-if="state === 'loading' && slots.placeholder"
      class="r-img__layer"
    >
      <slot name="placeholder" />
    </div>

    <div v-if="state === 'error'" class="r-img__layer">
      <slot name="error" />
    </div>

    <div v-if="state === 'loaded' && slots.default" class="r-img__overlay">
      <slot />
    </div>
  </div>
</template>

<style scoped>
.r-img {
  display: inline-block;
  position: relative;
  overflow: hidden;
  /* Inline-block + line-height: 0 prevents the natural baseline gap
     under <img> that puts a couple of px under the image when used
     inline next to text. */
  line-height: 0;
}

/* Image — defaults to width 100%, height auto so a logo with only
   `width` set keeps its natural aspect ratio. Adding `cover`/`contain`
   forces the height to fill the wrapper so object-fit takes effect. */
.r-img__image {
  display: block;
  width: 100%;
  height: auto;
  /* Fade in once loaded — the `--loaded` class on the wrapper flips
     opacity. While loading the image is still in the DOM (so onload
     can fire) but invisible. */
  opacity: 0;
  transition: opacity var(--r-motion-base) var(--r-motion-ease-out);
}
.r-img--loaded .r-img__image {
  opacity: 1;
}

.r-img--cover .r-img__image,
.r-img--contain .r-img__image {
  height: 100%;
}
.r-img--cover .r-img__image {
  object-fit: cover;
}
.r-img--contain .r-img__image {
  object-fit: contain;
}

/* Loading / error layer — absolutely positioned over the wrapper so
   it sits where the image would and disappears once the image lands.
   `inset: 0` works with the inline-block sizing. */
.r-img__layer {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  /* Layers inherit the wrapper's font-size (in case the consumer puts
     an MDI fallback icon inside). Reset line-height so text inside
     reads correctly — the wrapper sets it to 0 to suppress the baseline
     gap. */
  line-height: 1.4;
}

/* Default-slot overlay — sits over the loaded image. Caption /
   hover-CTA / shimmer-on-top. */
.r-img__overlay {
  position: absolute;
  inset: 0;
  line-height: 1.4;
}
</style>
