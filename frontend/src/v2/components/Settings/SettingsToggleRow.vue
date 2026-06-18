<script setup lang="ts">
// SettingsToggleRow — a clickable row used inside a settings section's
// toggle grid. Displays a label + description on the left and an
// `RSwitch` on the right. The whole row is the click target so users
// don't have to aim at the switch itself.
//
// The visual switch is `<RSwitch static>` — purely presentational, no
// nested button. The row's outer `<button role="switch">` owns the
// interaction (click, keyboard, aria-checked).
import { RSwitch } from "@v2/lib";
import { computed, useSlots } from "vue";

defineOptions({ inheritAttrs: false });

interface Props {
  modelValue: boolean;
  title: string;
  description?: string;
  disabled?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
  description: undefined,
  disabled: false,
});

const emit = defineEmits<{
  (e: "update:modelValue", value: boolean): void;
}>();

const slots = useSlots();
const ariaPressed = computed(() => props.modelValue);

function toggle() {
  if (props.disabled) return;
  emit("update:modelValue", !props.modelValue);
}
</script>

<template>
  <button
    type="button"
    role="switch"
    :aria-checked="ariaPressed"
    :aria-label="title"
    :disabled="disabled"
    class="r-v2-toggle-row"
    :class="{
      'r-v2-toggle-row--disabled': disabled,
      'r-v2-toggle-row--on': modelValue,
    }"
    @click="toggle"
  >
    <span class="r-v2-toggle-row__info">
      <span class="r-v2-toggle-row__label">{{ title }}</span>
      <span v-if="description" class="r-v2-toggle-row__desc">
        {{ description }}
      </span>
    </span>
    <!-- Optional inline control slot — for per-row secondary widgets
         (e.g. a "Compact / Extended" segmented control for the
         Library Snapshot widget toggle). Click events stop here so
         nested interactive controls don't bubble up and flip the row
         toggle; mousedown is stopped too so `<RSliderBtnGroup>`'s
         pointer-based active-pill animation doesn't trigger a row
         click on release. */
    -->
    <span
      v-if="slots.append"
      class="r-v2-toggle-row__append"
      @click.stop
      @mousedown.stop
      @keydown.stop
    >
      <slot name="append" />
    </span>
    <RSwitch
      :model-value="modelValue"
      :disabled="disabled"
      class="r-v2-toggle-row__switch"
      static
    />
  </button>
</template>

<style scoped>
.r-v2-toggle-row {
  display: flex;
  /* Centre the switch (and any `#append` control) against the row's
     full height instead of the label's baseline — when the row has
     both a label and a description, the trailing control should sit
     at the visual midpoint of the two-line block, not next to the
     label. */
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 16px;
  background: var(--r-color-bg-elevated);
  cursor: pointer;
  border: none;
  text-align: left;
  width: 100%;
  font-family: inherit;
  color: inherit;
  transition: background var(--r-motion-fast) var(--r-motion-ease-out);
}

.r-v2-toggle-row:hover:not(.r-v2-toggle-row--disabled) {
  background: var(--r-color-surface);
}

.r-v2-toggle-row--disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

.r-v2-toggle-row__info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.r-v2-toggle-row__label {
  font-size: 13px;
  font-weight: var(--r-font-weight-medium);
  color: var(--r-color-fg);
  transition: color var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-v2-toggle-row--on .r-v2-toggle-row__label {
  color: var(--r-color-brand-primary);
}

.r-v2-toggle-row__desc {
  font-size: 11px;
  color: var(--r-color-fg-muted);
  line-height: 1.4;
}

.r-v2-toggle-row__switch {
  flex-shrink: 0;
}

.r-v2-toggle-row__append {
  display: inline-flex;
  align-items: center;
  flex-shrink: 0;
}
</style>
