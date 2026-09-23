<script setup lang="ts">
import { computed, ref, watch } from "vue";
import {
  DEFAULT_PLATFORM_ICON,
  platformIconSrc,
} from "@/v2/composables/usePlatformIconCache/iconCache";
import RTooltip from "@/v2/lib/structural/RTooltip/RTooltip.vue";

defineOptions({ inheritAttrs: false });

interface Props {
  name?: string;
  slug?: string;
  fsSlug?: string;
  src?: string;
  size?: number | string;
  alt?: string;
  title?: string;
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

const resolvedSrc = computed(() =>
  platformIconSrc(props.slug ?? props.name, props.fsSlug, props.src),
);

const resolvedAlt = computed(
  () => props.alt || props.name || props.slug || props.fsSlug || "",
);

const tooltipText = computed(
  () => props.title ?? props.alt ?? props.name ?? props.slug ?? "",
);

const failed = ref(false);
watch(resolvedSrc, () => {
  failed.value = false;
});

const displaySrc = computed(() =>
  failed.value ? DEFAULT_PLATFORM_ICON : resolvedSrc.value,
);

function onImgError() {
  if (displaySrc.value !== DEFAULT_PLATFORM_ICON) {
    failed.value = true;
  }
}

const resolvedSize = computed(() =>
  typeof props.size === "number" ? `${props.size}px` : props.size,
);
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
      :alt="resolvedAlt"
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
