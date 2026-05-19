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
import { computed } from "vue";

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
  align-items: flex-start;
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

/* Nudge the static switch down by 2px so its track aligns with the
   label baseline — `align-items: flex-start` on the row otherwise
   parks the switch flush at the top, above the label. */
.r-v2-toggle-row__switch {
  margin-top: 2px;
  flex-shrink: 0;
}
</style>
