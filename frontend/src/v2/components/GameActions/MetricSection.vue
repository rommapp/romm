<script setup lang="ts">
// MetricSection — inline editor body for a single per-user metric
// (rating, difficulty, completion). Shared between MetricMenuBtn's
// popup (desktop ribbon) and GameMetricsSections' mobile status sheet.
// Renders a header (icon + label + live value), an RRating for 1..max
// scales or an RSlider for 0..100 percent, and a clear button.
//
// Emits `update:value` for the write and `close` on discrete picks
// (rating pick / clear) so a host popup can dismiss itself; the mobile
// sheet ignores `close` and stays open. The slider commits on drag-end
// only (no `close`), to avoid firing a write per pixel.
import { RIcon, RRating, RSlider } from "@v2/lib";
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
}

const props = withDefaults(defineProps<Props>(), {
  kind: "rating",
  max: 10,
  step: 5,
  disabled: false,
});

const emit = defineEmits<{
  (e: "update:value", v: number): void;
  (e: "close"): void;
}>();

const local = ref(props.value);
watch(
  () => props.value,
  (v) => {
    local.value = v;
  },
);

const liveLabel = computed(() => {
  if (local.value <= 0) return "—";
  return props.kind === "percent" ? `${local.value}%` : `${local.value}`;
});

function pickRating(n: number) {
  emit("update:value", n);
  emit("close");
}

function commitSlider() {
  if (local.value === props.value) return;
  emit("update:value", local.value);
}

function clear() {
  if (props.value !== 0) emit("update:value", 0);
  local.value = 0;
  emit("close");
}
</script>

<template>
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
      class="r-v2-metric-menu__rating"
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
</template>

<style scoped>
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

/* Shrink to the icon row's own width and centre it in the column,
   instead of stretching flush-left. No-op in the desktop popup, which
   already sizes to the row; centres it in the full-width mobile sheet. */
.r-v2-metric-menu__rating {
  align-self: center;
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
