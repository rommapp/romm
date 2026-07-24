<script setup lang="ts">
// MetricMenuBtn — picker for a per-user numeric metric on a ROM.
// Powers all three score controls in the GameActions ribbon: rating,
// difficulty (kind='rating'), and completion (kind='percent').
//
// Trigger: glass pill matching .r-v2-game-btn--surface so it sits in
// the action row without visual breaks. The popup body is a shared
// MetricSection (also used by the mobile status sheet). Picking a
// rating closes the popup; the slider commits on drag-end and keeps
// the popup open.
import { RIcon, RMenu } from "@v2/lib";
import { computed, ref } from "vue";
import MetricSection from "@/v2/components/GameActions/MetricSection.vue";

defineOptions({ inheritAttrs: false });

interface Props {
  kind?: "rating" | "percent";
  value: number;
  max?: number;
  step?: number;
  label: string;
  iconFull: string;
  iconEmpty: string;
  accent: string;
  disabled?: boolean;
  size?: "default" | "large";
}

const props = withDefaults(defineProps<Props>(), {
  kind: "rating",
  max: 10,
  step: 5,
  disabled: false,
  size: "large",
});

const emit = defineEmits<{
  (e: "update:value", v: number): void;
}>();

const open = ref(false);

const valueLabel = computed(() => {
  if (props.value <= 0) return "—";
  return props.kind === "percent" ? `${props.value}%` : `${props.value}`;
});
</script>

<template>
  <RMenu
    v-model="open"
    :offset="8"
    :close-on-content-click="false"
    :width="kind === 'percent' ? '300px' : 'auto'"
  >
    <template #activator="{ props: activatorProps }">
      <button
        v-bind="activatorProps"
        type="button"
        class="r-v2-metric-btn"
        :class="[
          `r-v2-metric-btn--${size}`,
          { 'r-v2-metric-btn--has-value': value > 0 },
        ]"
        :style="{ '--metric-accent': `var(--r-color-${accent})` }"
        :disabled="disabled"
        :aria-label="`${label}: ${value > 0 ? valueLabel : 'unset'}`"
      >
        <RIcon :icon="value > 0 ? iconFull : iconEmpty" />
        <span class="r-v2-metric-btn__value">{{ valueLabel }}</span>
      </button>
    </template>

    <MetricSection
      :kind="kind"
      :value="value"
      :max="max"
      :step="step"
      :label="label"
      :icon-full="iconFull"
      :icon-empty="iconEmpty"
      :accent="accent"
      @update:value="(v) => emit('update:value', v)"
      @close="open = false"
    />
  </RMenu>
</template>

<style scoped>
/* Trigger — parallels .r-v2-game-btn--surface so it sits in the
   action row without visual breaks. Translucent grey RTag-style
   surface, not the dark cover-overlay scrim. */
.r-v2-metric-btn {
  appearance: none;
  border: 1px solid var(--r-color-border-strong);
  background: var(--r-color-surface);
  color: var(--r-color-fg-secondary);
  display: inline-flex;
  align-items: center;
  gap: 8px;
  height: 44px;
  padding: 0 16px;
  border-radius: var(--r-radius-pill);
  cursor: pointer;
  font-family: inherit;
  font-weight: var(--r-font-weight-semibold);
  font-size: 14px;
  backdrop-filter: blur(20px);
  transition:
    background var(--r-motion-fast) var(--r-motion-ease-out),
    color var(--r-motion-fast) var(--r-motion-ease-out),
    border-color var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-v2-metric-btn :deep(.mdi) {
  font-size: 20px;
}
.r-v2-metric-btn--default {
  height: 40px;
  padding: 0 14px;
  font-size: 13px;
}
.r-v2-metric-btn--default :deep(.mdi) {
  font-size: 20px;
}
.r-v2-metric-btn:hover:not(:disabled) {
  background: var(--r-color-surface-hover);
  color: var(--r-color-fg);
}
.r-v2-metric-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.r-v2-metric-btn--has-value {
  color: var(--metric-accent);
}
.r-v2-metric-btn--has-value:hover:not(:disabled) {
  color: var(--metric-accent);
}
.r-v2-metric-btn__value {
  font-variant-numeric: tabular-nums;
  min-width: 1ch;
  text-align: center;
}
</style>
