<script setup lang="ts">
// Stat — KPI column: big value on top, small uppercase label below.
// Feature component; InfoPanel and the gallery hero cards reuse it, but
// it's not general enough to be a design-system primitive.
import { useAnimatedNumber } from "@/v2/composables/useAnimatedNumber";

defineOptions({ inheritAttrs: false });

interface Props {
  value?: string | number;
  label?: string;
}

const props = withDefaults(defineProps<Props>(), {
  value: undefined,
  label: undefined,
});

// A count rolls up to its value; anything already formatted (a size, a date)
// is printed as it comes.
const text = useAnimatedNumber(() => props.value);
</script>

<template>
  <div class="stat">
    <div class="stat__value">
      <slot>{{ text }}</slot>
    </div>
    <div class="stat__label">
      <slot name="label">{{ label }}</slot>
    </div>
  </div>
</template>

<style scoped>
.stat {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.stat__value {
  font-size: var(--r-font-size-2xl);
  font-weight: var(--r-font-weight-bold);
  color: var(--r-color-fg);
  line-height: 1;
  font-variant-numeric: tabular-nums;
}

.stat__label {
  font-size: 10px;
  font-weight: var(--r-font-weight-bold);
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--r-color-fg-muted);
}
</style>
