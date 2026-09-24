<script setup lang="ts">
// RSkeletonBlock — shimmer placeholder. Owns shape, sizing, and the
// animation style directly — no skeleton-loader abstraction.
//
// `inheritAttrs` stays at the Vue default so a caller's positioning class
// merges into the root span instead of being silently dropped.

interface Props {
  width?: string | number;
  height?: string | number;
  rounded?: string;
  circle?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
  width: "100%",
  height: "1rem",
  rounded: "sm",
  circle: false,
});

const resolveSize = (v: string | number) =>
  typeof v === "number" ? `${v}px` : v;

const style = {
  width: resolveSize(props.width),
  height: resolveSize(props.height),
  borderRadius: props.circle ? "50%" : `var(--r-radius-${props.rounded})`,
};
</script>

<template>
  <span class="r-skeleton" :style="style" :aria-hidden="true" />
</template>

<style scoped>
.r-skeleton {
  display: inline-block;
  position: relative;
  overflow: hidden;
  background-color: var(--r-color-border);
}

.r-skeleton::after {
  content: "";
  position: absolute;
  inset: 0;
  transform: translateX(-100%);
  background: linear-gradient(
    90deg,
    transparent,
    var(--r-color-shimmer-sweep),
    transparent
  );
  animation: r-skeleton-shimmer 1.4s infinite;
}

@keyframes r-skeleton-shimmer {
  100% {
    transform: translateX(100%);
  }
}

@media (prefers-reduced-motion: reduce) {
  .r-skeleton::after {
    animation: none;
  }
}
</style>
