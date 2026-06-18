<script setup lang="ts">
// RSpinner — small indeterminate progress indicator. Thin convenience wrapper
// over RProgressCircular with compact defaults suitable for inline loading
// states (buttons, list items, toolbars).
import RProgressCircular from "@/v2/lib/primitives/RProgressCircular/RProgressCircular.vue";

defineOptions({ inheritAttrs: false });

interface Props {
  size?: number | string;
  width?: number | string;
  color?: string;
}

withDefaults(defineProps<Props>(), {
  size: 18,
  width: 2,
  color: "primary",
});
</script>

<template>
  <RProgressCircular
    v-bind="$attrs"
    indeterminate
    :size="size"
    :width="width"
    :color="color"
  />
</template>
