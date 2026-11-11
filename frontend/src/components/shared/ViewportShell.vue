<script setup lang="ts">
// ViewportShell: a one-viewport frame for views that scroll an inner container.
// The document never scrolls, so iOS Safari has nothing to draw under its
// status bar, and the inner scroller runs under the app's translucent bars.
import { useResizeObserver } from "@vueuse/core";
import { onBeforeUnmount, onMounted, ref, watch } from "vue";

defineOptions({ inheritAttrs: false });

interface Props {
  /** The inner scroll container, whose scrollbar the top bar stops short of. */
  scroller?: HTMLElement | null;
}

const props = withDefaults(defineProps<Props>(), { scroller: null });

defineSlots<{ default(): unknown }>();

const el = ref<HTMLElement | null>(null);
defineExpose({ el });

// Pixel rounding can still overflow the document, adding a second scrollbar.
let prevBodyOverflow: string | null = null;
onMounted(() => {
  prevBodyOverflow = document.body.style.overflow;
  document.body.style.overflow = "hidden";
});

// Published on <html> so the fixed top bar can stop short of the scrollbar,
// which it would otherwise cover.
const SCROLLBAR_W_VAR = "--r-shell-scrollbar-w";
const scrollbarWidth = ref(0);
useResizeObserver(
  () => props.scroller,
  () => {
    const scroller = props.scroller;
    if (scroller) {
      scrollbarWidth.value = scroller.offsetWidth - scroller.clientWidth;
    }
  },
);
watch(scrollbarWidth, (w) => {
  document.documentElement.style.setProperty(SCROLLBAR_W_VAR, `${w}px`);
});

onBeforeUnmount(() => {
  document.body.style.overflow = prevBodyOverflow ?? "";
  prevBodyOverflow = null;
  document.documentElement.style.removeProperty(SCROLLBAR_W_VAR);
});
</script>

<template>
  <section ref="el" v-bind="$attrs" class="r-viewport-shell">
    <slot />
  </section>
</template>

<style scoped>
.r-viewport-shell {
  flex: 1;
  display: flex;
  overflow: hidden;
  position: relative;
  /* Not `height: 100%`, which doesn't always resolve inside the flex <main>. */
  height: 100vh;
  height: 100dvh;
  /* Run up under the fixed top bar, whose height <main> reserves as padding. */
  margin-top: calc(-1 * var(--r-nav-h));
  /* Out of the app shell's safe-area padding to the screen edges, so pinned
     glass spans them; the scroller pads back in. */
  margin-inline: calc(-1 * var(--r-safe-l)) calc(-1 * var(--r-safe-r));
}

/* Cancels <main>'s bottom tab bar padding so the frame stays one viewport. */
html[data-bp~="sm-and-down"] .r-viewport-shell {
  margin-bottom: calc(-1 * (var(--r-bottom-nav-h) + var(--r-safe-b)));
}
</style>
