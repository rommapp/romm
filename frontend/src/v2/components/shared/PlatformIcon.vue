<script setup lang="ts">
import { RPlatformIcon } from "@v2/lib";
import { computed } from "vue";
import {
  DEFAULT_PLATFORM_ICON,
  platformIconSrc,
} from "@/v2/composables/usePlatformIconCache/iconCache";

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
</script>

<template>
  <RPlatformIcon
    v-bind="$attrs"
    :src="resolvedSrc"
    :fallback-src="DEFAULT_PLATFORM_ICON"
    :size="size"
    :alt="resolvedAlt"
    :title="tooltipText"
    :show-tooltip="showTooltip"
  />
</template>
