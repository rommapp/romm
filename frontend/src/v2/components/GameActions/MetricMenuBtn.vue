<script setup lang="ts">
// MetricMenuBtn — picker for a per-user numeric metric on a ROM.
// Powers all three score controls in the GameActions ribbon: rating,
// difficulty (kind='rating'), and completion (kind='percent').
//
// Trigger: glass pill matching .r-v2-game-btn--surface so it sits in
// the action row without visual breaks. Popup hosts an RRating for
// 1..max scales (rating, difficulty) or an RSlider with a thumb-following
// bubble for 0..100 percent ranges (completion). The slider commits on
// drag-end to avoid firing a write per pixel; the rating picker commits
// on click and closes the popup.
//
// Generic: caller supplies the icon pair, accent color, label and
// kind/range. No domain knowledge — feature composite because it's only
// consumed by the GameActions feature for now.
import { RIcon, RMenu, RRating, RSlider } from "@v2/lib";
import { computed, ref, watch } from "vue";
import { useI18n } from "vue-i18n";

defineOptions({ inheritAttrs: false });

const { t } = useI18n();

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
const local = ref(props.value);

watch(
  () => props.value,
  (v) => {
    local.value = v;
  },
);
watch(open, (v) => {
  if (v) local.value = props.value;
});

const valueLabel = computed(() => {
  if (props.value <= 0) return "—";
  return props.kind === "percent" ? `${props.value}%` : `${props.value}`;
});

const liveLabel = computed(() => {
  if (local.value <= 0) return "—";
  return props.kind === "percent" ? `${local.value}%` : `${local.value}`;
});

function pickRating(n: number) {
  emit("update:value", n);
  open.value = false;
}

function commitSlider() {
  if (local.value === props.value) return;
  emit("update:value", local.value);
}

function clear() {
  if (props.value !== 0) emit("update:value", 0);
  local.value = 0;
  open.value = false;
}
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

    <div
      class="r-v2-metric-menu"
      :style="{ '--metric-accent': `var(--r-color-${accent})` }"
    >
      <div class="r-v2-metric-menu__header">
        <RIcon :icon="local > 0 ? iconFull : iconEmpty" />
        <span class="r-v2-metric-menu__label">{{ label }}</span>
        <span class="r-v2-metric-menu__current">{{ liveLabel }}</span>
      </div>

      <RRating
        v-if="kind === 'rating'"
        :model-value="value"
        :length="max"
        :empty-icon="iconEmpty"
        :full-icon="iconFull"
        :color="accent"
        :active-color="accent"
        size="small"
        density="compact"
        hover
        @update:model-value="pickRating"
      />

      <RSlider
        v-else
        v-model="local"
        :min="0"
        :max="100"
        :step="step"
        :color="accent"
        value-position="none"
        value-suffix="%"
        @end="commitSlider"
      />

      <button
        type="button"
        class="r-v2-metric-menu__clear"
        :disabled="value === 0"
        @click="clear"
      >
        <RIcon icon="mdi-close" size="14" />
        {{ t("rom.clear-field", { field: label.toLowerCase() }) }}
      </button>
    </div>
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
  -webkit-backdrop-filter: blur(20px);
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

/* Menu */
.r-v2-metric-menu {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 10px;
}
.r-v2-metric-menu__header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 0 4px;
  font-size: 13px;
  font-weight: var(--r-font-weight-semibold);
}
.r-v2-metric-menu__header :deep(.mdi) {
  font-size: 16px;
  color: var(--metric-accent);
}
.r-v2-metric-menu__label {
  flex: 1;
  color: var(--r-color-fg);
}
.r-v2-metric-menu__current {
  color: var(--r-color-fg-secondary);
  font-variant-numeric: tabular-nums;
  min-width: 4ch;
  text-align: right;
}

.r-v2-metric-menu__clear {
  appearance: none;
  border: 0;
  background: transparent;
  color: var(--r-color-fg-muted);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  padding: 6px;
  border-radius: var(--r-radius-sm);
  cursor: pointer;
  font-family: inherit;
  font-size: 12px;
  font-weight: var(--r-font-weight-medium);
  transition:
    background var(--r-motion-fast) var(--r-motion-ease-out),
    color var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-v2-metric-menu__clear:hover:not(:disabled) {
  background: var(--r-color-surface);
  color: var(--r-color-fg);
}
.r-v2-metric-menu__clear:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
</style>
