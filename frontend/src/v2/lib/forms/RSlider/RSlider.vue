<script setup lang="ts">
// RSlider — Vuetify-free. Styled native `<input type="range">`. We
// paint the track / fill / thumb via the browser's native pseudo-
// elements (`::-webkit-slider-runnable-track`, `::-webkit-slider-thumb`,
// and their `::-moz-range-*` counterparts) — no overlay element fights
// the input for pointer events, so dragging "just works" by definition.
//
// Layouts via `valuePosition`:
//   • "none"   default; consumer renders the value externally
//   • "left"   pill to the left of the track
//   • "right"  pill to the right
//   • "thumb"  floating pill above the thumb that follows the drag
//
// `@end` fires on pointer release / blur — handy for commit-on-end
// patterns where every intermediate `update:modelValue` is just preview.
import { computed, ref } from "vue";

defineOptions({ inheritAttrs: false });

interface Props {
  modelValue?: number;
  min?: number;
  max?: number;
  step?: number;
  /** Tone keyword (`primary`, `success`, …) or any CSS colour. */
  color?: string;
  disabled?: boolean;
  readonly?: boolean;
  valuePosition?: "none" | "left" | "right" | "thumb";
  valueSuffix?: string;
  /** Render tick dots along the track (every `step`). */
  showTicks?: boolean;
  /** ARIA label when no visible label exists. */
  ariaLabel?: string;
}

const props = withDefaults(defineProps<Props>(), {
  modelValue: 0,
  min: 0,
  max: 100,
  step: 1,
  color: "primary",
  disabled: false,
  readonly: false,
  valuePosition: "none",
  valueSuffix: "",
  showTicks: false,
  ariaLabel: undefined,
});

const emit = defineEmits<{
  (e: "update:modelValue", value: number): void;
  (e: "start", value: number): void;
  (e: "end", value: number): void;
}>();

const TONE_MAP: Record<string, string> = {
  primary: "var(--r-color-brand-primary)",
  secondary: "var(--r-color-brand-secondary)",
  accent: "var(--r-color-brand-accent)",
  success: "var(--r-color-success)",
  warning: "var(--r-color-warning)",
  danger: "var(--r-color-danger)",
  error: "var(--r-color-danger)",
  info: "var(--r-color-info)",
  "romm-red": "var(--r-color-romm-red)",
  "romm-green": "var(--r-color-romm-green)",
  "romm-blue": "var(--r-color-romm-blue)",
  "romm-gold": "var(--r-color-romm-gold)",
};
const accent = computed(() => {
  // 1. Keyword shorthands (`primary`, `success`, …) → mapped token.
  if (TONE_MAP[props.color]) return TONE_MAP[props.color];
  // 2. Kebab-case token form ("brand-primary", "warning", "romm-gold"
  //    — anything callers pass to match the rest of the lib's `--r-color-*`
  //    vocabulary). Wrap as `var(--r-color-X, X)` so the fallback still
  //    yields a valid colour if the var isn't defined.
  if (/^[a-z][a-z0-9-]*$/i.test(props.color)) {
    return `var(--r-color-${props.color}, ${props.color})`;
  }
  // 3. Arbitrary CSS colour ("#ff0", "rgb(…)", "tomato"): pass through.
  return props.color ?? TONE_MAP.primary;
});

const percent = computed(() => {
  const range = props.max - props.min || 1;
  return Math.max(
    0,
    Math.min(100, ((props.modelValue - props.min) / range) * 100),
  );
});
const formatted = computed(() => `${props.modelValue}${props.valueSuffix}`);

const showThumbBubble = computed(() => props.valuePosition === "thumb");
const showLeftBadge = computed(() => props.valuePosition === "left");
const showRightBadge = computed(() => props.valuePosition === "right");

// One dot per step — capped at 60 so step=1 over a 0..10000 range
// doesn't pepper the track.
const ticks = computed<{ percent: number; filled: boolean }[]>(() => {
  if (!props.showTicks) return [];
  const range = props.max - props.min || 1;
  const stepCount = Math.min(60, Math.floor(range / props.step));
  const arr: { percent: number; filled: boolean }[] = [];
  for (let i = 0; i <= stepCount; i++) {
    const value = props.min + i * props.step;
    const p = ((value - props.min) / range) * 100;
    arr.push({ percent: p, filled: value <= props.modelValue });
  }
  return arr;
});

const dragging = ref(false);

function onInput(evt: Event) {
  const v = Number((evt.target as HTMLInputElement).value);
  emit("update:modelValue", v);
}
function onPointerDown() {
  if (props.disabled || props.readonly) return;
  dragging.value = true;
  emit("start", props.modelValue);
}
function onPointerUp() {
  if (!dragging.value) return;
  dragging.value = false;
  emit("end", props.modelValue);
}
function onChange() {
  emit("end", props.modelValue);
}
</script>

<template>
  <div
    v-bind="$attrs"
    class="r-slider"
    :class="[
      `r-slider--pos-${valuePosition}`,
      {
        'r-slider--disabled': disabled,
        'r-slider--readonly': readonly,
        'r-slider--dragging': dragging,
      },
    ]"
    :style="{
      '--r-slider-accent': accent,
      '--r-slider-percent': `${percent}%`,
      '--r-slider-percent-num': String(percent),
    }"
  >
    <span v-if="showLeftBadge" class="r-slider__badge r-slider__badge--left">
      <slot name="value" :value="modelValue" :percent="percent">
        {{ formatted }}
      </slot>
    </span>

    <div class="r-slider__core">
      <input
        type="range"
        class="r-slider__native"
        :value="modelValue"
        :min="min"
        :max="max"
        :step="step"
        :disabled="disabled"
        :aria-label="ariaLabel"
        :aria-valuemin="min"
        :aria-valuemax="max"
        :aria-valuenow="modelValue"
        :aria-orientation="'horizontal'"
        :aria-readonly="readonly || undefined"
        @input="onInput"
        @change="onChange"
        @pointerdown="onPointerDown"
        @pointerup="onPointerUp"
        @pointercancel="onPointerUp"
      />
      <!-- Ticks — purely decorative overlay; pointer events pass through. -->
      <span v-if="showTicks" class="r-slider__ticks" aria-hidden="true">
        <span
          v-for="(t, i) in ticks"
          :key="i"
          class="r-slider__tick"
          :class="{ 'r-slider__tick--filled': t.filled }"
          :style="{ left: `${t.percent}%` }"
        />
      </span>
      <!-- Floating bubble that follows the thumb. Sits above the track,
           pointer-events: none so it never intercepts drag. The `left`
           formula compensates for the thumb's 14 px width — the native
           thumb's centre travels from 7 px to (width − 7 px), so the
           bubble lines up at every percent instead of overshooting the
           ends. -->
      <span
        v-if="showThumbBubble"
        class="r-slider__bubble"
        aria-hidden="true"
        :style="{
          left: `calc(7px + (100% - 14px) * var(--r-slider-percent-num) / 100)`,
        }"
      >
        <slot name="value" :value="modelValue" :percent="percent">
          {{ formatted }}
        </slot>
      </span>
    </div>

    <span v-if="showRightBadge" class="r-slider__badge r-slider__badge--right">
      <slot name="value" :value="modelValue" :percent="percent">
        {{ formatted }}
      </slot>
    </span>
  </div>
</template>

<style scoped>
.r-slider {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
  --r-slider-accent: var(--r-color-brand-primary);
  --r-slider-percent: 0%;
}

.r-slider--disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.r-slider__core {
  position: relative;
  flex: 1 1 auto;
  min-width: 0;
  /* Enough vertical room for the thumb + the floating bubble above it. */
  height: 32px;
  display: flex;
  align-items: center;
}

/* ── Native input — the actual interactive element. Pseudo-elements
   paint the track + thumb, so the input IS the visible chrome. The
   gradient on the runnable track gives us the "fill" effect from
   start → thumb without an overlay div. ──────────────────────────── */
.r-slider__native {
  appearance: none;
  -webkit-appearance: none;
  width: 100%;
  height: 18px;
  margin: 0;
  padding: 0;
  background: transparent;
  cursor: pointer;
  outline: 0;
}
.r-slider--disabled .r-slider__native {
  cursor: not-allowed;
}
.r-slider--readonly .r-slider__native {
  pointer-events: none;
}

/* WebKit / Blink — track */
.r-slider__native::-webkit-slider-runnable-track {
  height: 5px;
  border: 1px solid var(--r-color-panel-border);
  border-radius: 999px;
  background: linear-gradient(
    90deg,
    var(--r-slider-accent) 0,
    color-mix(in srgb, var(--r-slider-accent), white 18%)
      var(--r-slider-percent),
    var(--r-color-bg-elevated) var(--r-slider-percent)
  );
  transition: box-shadow var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-slider:not(.r-slider--disabled):not(.r-slider--readonly):hover
  .r-slider__native::-webkit-slider-runnable-track,
.r-slider--dragging:not(.r-slider--disabled):not(.r-slider--readonly)
  .r-slider__native::-webkit-slider-runnable-track,
.r-slider:not(.r-slider--disabled):not(.r-slider--readonly):focus-within
  .r-slider__native::-webkit-slider-runnable-track {
  box-shadow: 0 0 18px
    color-mix(in srgb, var(--r-slider-accent) 55%, transparent);
}

/* WebKit — thumb. `margin-top` centres it on the 5 px track (thumb
   height − track height = 14 − 5 = 9 → −9/2 = −4.5; the border adds 2
   px each side so we end at −5.5). */
.r-slider__native::-webkit-slider-thumb {
  appearance: none;
  -webkit-appearance: none;
  width: 14px;
  height: 14px;
  background: var(--r-slider-accent);
  border: 2px solid var(--r-color-fg);
  border-radius: 50%;
  margin-top: -5.5px;
  box-shadow: var(--r-elev-1);
  cursor: pointer;
  transition:
    transform var(--r-motion-fast) cubic-bezier(0.34, 1.56, 0.64, 1),
    box-shadow var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-slider:not(.r-slider--disabled):not(.r-slider--readonly)
  .r-slider__native:hover::-webkit-slider-thumb,
.r-slider:not(.r-slider--disabled):not(.r-slider--readonly)
  .r-slider__native:focus::-webkit-slider-thumb {
  transform: scale(1.18);
  box-shadow:
    var(--r-elev-2),
    0 0 0 6px color-mix(in srgb, var(--r-slider-accent) 25%, transparent);
}
.r-slider--dragging:not(.r-slider--disabled):not(.r-slider--readonly)
  .r-slider__native::-webkit-slider-thumb {
  transform: scale(1.28);
  background: color-mix(in srgb, var(--r-slider-accent), white 14%);
}

/* Firefox — track */
.r-slider__native::-moz-range-track {
  height: 5px;
  border: 1px solid var(--r-color-panel-border);
  border-radius: 999px;
  background: var(--r-color-bg-elevated);
}
/* Firefox — fill progress (active portion before the thumb). */
.r-slider__native::-moz-range-progress {
  height: 5px;
  border-radius: 999px;
  background: linear-gradient(
    90deg,
    var(--r-slider-accent),
    color-mix(in srgb, var(--r-slider-accent), white 18%)
  );
}
/* Firefox — thumb */
.r-slider__native::-moz-range-thumb {
  width: 14px;
  height: 14px;
  background: var(--r-slider-accent);
  border: 2px solid var(--r-color-fg);
  border-radius: 50%;
  box-shadow: var(--r-elev-1);
  cursor: pointer;
  transition:
    transform var(--r-motion-fast) cubic-bezier(0.34, 1.56, 0.64, 1),
    box-shadow var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-slider:not(.r-slider--disabled):not(.r-slider--readonly)
  .r-slider__native:hover::-moz-range-thumb,
.r-slider:not(.r-slider--disabled):not(.r-slider--readonly)
  .r-slider__native:focus::-moz-range-thumb {
  transform: scale(1.18);
  box-shadow:
    var(--r-elev-2),
    0 0 0 6px color-mix(in srgb, var(--r-slider-accent) 25%, transparent);
}
.r-slider--dragging:not(.r-slider--disabled):not(.r-slider--readonly)
  .r-slider__native::-moz-range-thumb {
  transform: scale(1.28);
  background: color-mix(in srgb, var(--r-slider-accent), white 14%);
}

/* Modality-gated keyboard focus ring. */
html[data-input="key"] .r-slider__native:focus::-webkit-slider-thumb,
html[data-input="pad"] .r-slider__native:focus::-webkit-slider-thumb {
  outline: 2px solid var(--r-slider-accent);
  outline-offset: 3px;
}

/* ── Ticks — overlaid dots, no pointer events. ─────────────────── */
.r-slider__ticks {
  position: absolute;
  inset: 0;
  display: block;
  pointer-events: none;
}
.r-slider__tick {
  position: absolute;
  top: 50%;
  width: 3px;
  height: 3px;
  border-radius: 50%;
  background: var(--r-color-fg-faint);
  transform: translate(-50%, -50%);
  opacity: 0.7;
}
.r-slider__tick--filled {
  background: color-mix(in srgb, var(--r-color-fg) 70%, transparent);
  opacity: 1;
}

/* ── Side badge (left / right) ────────────────────────────────── */
.r-slider__badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 48px;
  padding: 3px 10px;
  font-size: 12px;
  font-weight: var(--r-font-weight-semibold);
  font-variant-numeric: tabular-nums;
  background: var(--r-color-bg-elevated);
  border: 1px solid var(--r-color-panel-border);
  border-radius: 999px;
  color: var(--r-color-fg-secondary);
  flex-shrink: 0;
  transition:
    border-color var(--r-motion-fast) var(--r-motion-ease-out),
    color var(--r-motion-fast) var(--r-motion-ease-out),
    background var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-slider:not(.r-slider--disabled):not(.r-slider--readonly):hover
  .r-slider__badge,
.r-slider--dragging:not(.r-slider--disabled):not(.r-slider--readonly)
  .r-slider__badge,
.r-slider:not(.r-slider--disabled):not(.r-slider--readonly):focus-within
  .r-slider__badge {
  border-color: color-mix(in srgb, var(--r-slider-accent) 55%, transparent);
  color: var(--r-color-fg);
  background: color-mix(
    in srgb,
    var(--r-slider-accent) 12%,
    var(--r-color-bg-elevated)
  );
}
.r-slider--disabled .r-slider__badge,
.r-slider--readonly .r-slider__badge {
  border-color: var(--r-color-panel-border);
  background: var(--r-color-bg-elevated);
  color: var(--r-color-fg-secondary);
}

/* ── Floating thumb bubble — sits above the track, anchored to the
   current percent. Pointer events disabled so it doesn't block drag. */
.r-slider__bubble {
  position: absolute;
  bottom: calc(50% + 12px);
  transform: translateX(-50%);
  min-width: 40px;
  padding: 3px 10px;
  font-size: 11.5px;
  font-weight: var(--r-font-weight-semibold);
  font-variant-numeric: tabular-nums;
  color: var(--r-color-fg);
  background: linear-gradient(
    180deg,
    color-mix(in srgb, var(--r-slider-accent), white 18%),
    var(--r-slider-accent)
  );
  border-radius: 999px;
  box-shadow:
    0 4px 12px color-mix(in srgb, var(--r-slider-accent) 50%, transparent),
    inset 0 0 0 1px color-mix(in srgb, var(--r-color-fg) 18%, transparent);
  white-space: nowrap;
  pointer-events: none;
  transition:
    transform var(--r-motion-fast) cubic-bezier(0.34, 1.56, 0.64, 1),
    box-shadow var(--r-motion-fast) var(--r-motion-ease-out),
    left 0s;
}
.r-slider__bubble::after {
  content: "";
  position: absolute;
  bottom: -3px;
  left: 50%;
  width: 8px;
  height: 8px;
  background: var(--r-slider-accent);
  transform: translateX(-50%) rotate(45deg);
  border-bottom-right-radius: 2px;
  z-index: -1;
}
.r-slider--dragging .r-slider__bubble {
  transform: translateX(-50%) translateY(-2px) scale(1.04);
  box-shadow:
    0 6px 18px color-mix(in srgb, var(--r-slider-accent) 62%, transparent),
    inset 0 0 0 1px color-mix(in srgb, var(--r-color-fg) 22%, transparent);
}

/* ── Reduced motion ──────────────────────────────────────────── */
@media (prefers-reduced-motion: reduce) {
  .r-slider__native::-webkit-slider-thumb,
  .r-slider__native::-moz-range-thumb,
  .r-slider__bubble,
  .r-slider__badge {
    transition: none !important;
  }
}
</style>
