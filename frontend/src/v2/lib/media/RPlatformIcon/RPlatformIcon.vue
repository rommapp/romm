<script setup lang="ts">
import { computed, ref, watch } from "vue";
import RTooltip from "@/v2/lib/structural/RTooltip/RTooltip.vue";

defineOptions({ inheritAttrs: false });

interface Props {
  src: string;
  /** Used when `src` fails to paint. Omit to leave the broken image. */
  fallbackSrc?: string;
  size?: number | string;
  alt?: string;
  title?: string;
  showTooltip?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
  fallbackSrc: undefined,
  size: 28,
  alt: "",
  title: undefined,
  showTooltip: true,
});

const failed = ref(false);
watch(
  () => props.src,
  () => {
    failed.value = false;
  },
);

const displaySrc = computed(() =>
  failed.value && props.fallbackSrc ? props.fallbackSrc : props.src,
);

function onImgError() {
  if (props.fallbackSrc && displaySrc.value !== props.fallbackSrc) {
    failed.value = true;
  }
}

const resolvedSize = computed(() =>
  typeof props.size === "number" ? `${props.size}px` : props.size,
);

const tooltipText = computed(() => props.title ?? props.alt ?? "");
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
      :alt="alt"
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
