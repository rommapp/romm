<script setup lang="ts">
// RCheckbox — native `<input type="checkbox">` hidden
// inside a `<label>` so the whole row is the click target — no
// "ghost tap area" around the box needed. The visible box renders at
// its true size and the `gap` between box and label reads as a real
// margin, not a centring artefact.
//
// Variants:
//   • `size` — `xs / sm / md / lg` ladder driven by CSS vars.
//   • `shape` — `square / rounded / circle` (overrides the radius).
//   • `color` — TONE_MAP across the lib; drives the check fill +
//     active border + ring.
//   • `variant` — `box` (default) or `card`. Card wraps box + body
//     in a bordered surface that flips to a brand-tinted background
//     when checked. Designed for "pick one" choices with subtitles.
//
// `subtitle` lives under the label in the body — handy in card
// variant, optional in box variant. Slots `#default` (label) and
// `#subtitle` win over the props.
//
// Indeterminate is a DOM-only state (no HTML attribute) — synced
// via a ref on every prop change.
//
// Multi-state (`states`) is an opt-in N-value mode driven by its own
// `stateValue` model, leaving the boolean `modelValue` path untouched.
// Pass an ordered list of states (first = empty / unchecked); each click
// cycles to the next, wrapping around. A state with a `color` paints the
// box; a state with an `icon` shows that mdi glyph (otherwise the check
// tick), all with the same draw-in / pop flourish the check uses.
import { computed, onMounted, ref, useSlots, watch } from "vue";
import RIcon from "../../primitives/RIcon/RIcon.vue";
import type { RCheckboxState } from "./types";

defineOptions({ inheritAttrs: false });

interface Props {
  modelValue?: boolean | null;
  label?: string;
  /** Secondary line under the label — most useful in `variant="card"`. */
  subtitle?: string;
  disabled?: boolean;
  indeterminate?: boolean;
  /** Opt into N-state cycling. Ordered list, first entry = empty state.
   *  The current value is driven by `stateValue`. */
  states?: RCheckboxState[];
  /** Current multi-state value (only read when `states` is set). */
  stateValue?: string;
  /** Accessible name for a labelless checkbox (e.g. matrix cells). */
  ariaLabel?: string;
  /** Reserve vertical space for error messages. */
  hideDetails?: boolean | "auto";
  size?: "xs" | "sm" | "md" | "lg";
  shape?: "square" | "rounded" | "circle";
  /** Tone for the check fill + active border. */
  color?: string;
  variant?: "box" | "card";
  /** Box-only mode — drops the row's vertical breathing padding (4px
   *  top/bottom) and the box↔label gap so the checkbox can be
   *  positioned absolutely as a tight square. Use when the consumer
   *  owns the surrounding chrome (e.g. a GameCard overlay or a
   *  list-row checkbox column). Doesn't strip the label itself —
   *  if you omit the label and slots, only the box renders. */
  bare?: boolean;
  /** Error tone — red box + red label. */
  error?: boolean;
  errorMessages?: string | string[];
}

const props = withDefaults(defineProps<Props>(), {
  modelValue: false,
  label: undefined,
  subtitle: undefined,
  disabled: false,
  indeterminate: false,
  states: undefined,
  stateValue: undefined,
  ariaLabel: undefined,
  hideDetails: "auto",
  size: "md",
  shape: "square",
  color: "primary",
  variant: "box",
  bare: false,
  error: false,
  errorMessages: () => [],
});

const emit = defineEmits<{
  (e: "update:modelValue", value: boolean): void;
  (e: "update:stateValue", value: string): void;
}>();

const slots = useSlots();
const inputRef = ref<HTMLInputElement | null>(null);

// ── Multi-state ────────────────────────────────────────────────
const isMulti = computed(() => !!props.states && props.states.length > 0);
const currentIndex = computed(() => {
  if (!props.states) return 0;
  const i = props.states.findIndex((s) => s.value === props.stateValue);
  return i >= 0 ? i : 0;
});
const currentState = computed(() => props.states?.[currentIndex.value]);
// Index 0 is the empty / unchecked state; anything past it fills the box.
const isMultiActive = computed(() => isMulti.value && currentIndex.value > 0);
const multiIcon = computed(() => currentState.value?.icon);
const showMultiIcon = computed(() => isMultiActive.value && !!multiIcon.value);
const showMultiCheck = computed(() => isMultiActive.value && !multiIcon.value);

const isChecked = computed(() => !isMulti.value && props.modelValue === true);

// `indeterminate` has no HTML attribute — must be set via the DOM
// property on the input. A non-binary multi-state (a coloured icon state)
// also reports as "mixed" for assistive tech. Sync on mount + on flip.
function syncIndeterminate() {
  if (inputRef.value) {
    inputRef.value.indeterminate = !!props.indeterminate || showMultiIcon.value;
  }
}
onMounted(syncIndeterminate);
watch([() => props.indeterminate, showMultiIcon], syncIndeterminate);

function onChange(evt: Event) {
  if (isMulti.value && props.states) {
    const next = props.states[(currentIndex.value + 1) % props.states.length];
    emit("update:stateValue", next.value);
    return;
  }
  emit("update:modelValue", (evt.target as HTMLInputElement).checked);
}

// ── Tone resolver ──────────────────────────────────────────────
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
const resolvedColor = computed<string>(
  () => TONE_MAP[props.color] ?? props.color ?? TONE_MAP.primary,
);
// Fill colour for the active box — the current multi-state's tone when
// multi, else the `color` prop (2-state checked / indeterminate).
const fillColor = computed<string>(() => {
  const c = currentState.value?.color;
  return isMultiActive.value && c ? (TONE_MAP[c] ?? c) : resolvedColor.value;
});

// Multi-state icon size mirrors the per-size --r-cb-icon ladder so the
// custom glyph matches the built-in check / minus footprint.
const ICON_PX: Record<string, number> = { xs: 10, sm: 12, md: 14, lg: 16 };
const multiIconSize = computed(() => ICON_PX[props.size] ?? 14);

// ── Error message normalisation ───────────────────────────────
const messages = computed<string[]>(() => {
  if (!props.error) return [];
  const m = props.errorMessages;
  if (Array.isArray(m)) return m;
  return m ? [m] : [];
});

const showDetailsRow = computed(() => {
  if (props.hideDetails === true) return false;
  if (props.hideDetails === "auto") return messages.value.length > 0;
  return true;
});

const hasSubtitle = computed(() => !!(props.subtitle || slots.subtitle));
const hasLabel = computed(
  () => !!(props.label || slots.default || hasSubtitle.value),
);
</script>

<template>
  <div
    v-bind="$attrs"
    class="r-checkbox-wrap"
    :class="[
      `r-checkbox--size-${size}`,
      `r-checkbox--shape-${shape}`,
      `r-checkbox--variant-${variant}`,
      {
        'r-checkbox--checked': isChecked,
        'r-checkbox--indeterminate': indeterminate,
        'r-checkbox--multi-active': isMultiActive,
        'r-checkbox--multi-check': showMultiCheck,
        'r-checkbox--multi-icon': showMultiIcon,
        'r-checkbox--disabled': disabled,
        'r-checkbox--error': error,
        'r-checkbox--has-subtitle': hasSubtitle,
        'r-checkbox--bare': bare,
      },
    ]"
    :style="{
      '--r-cb-color': resolvedColor,
      '--r-cb-fill': fillColor,
    }"
  >
    <!-- eslint-disable-next-line vuejs-accessibility/label-has-for -- the native checkbox input is nested inside this label, a valid control association -->
    <label class="r-checkbox">
      <!-- Native input — visually hidden but kept in the layout for
           form submission, keyboard, and screen reader support. -->
      <input
        ref="inputRef"
        type="checkbox"
        class="r-checkbox__input"
        :checked="isChecked || isMultiActive"
        :disabled="disabled"
        :aria-label="ariaLabel"
        @change="onChange"
      />
      <span class="r-checkbox__box" aria-hidden="true">
        <!-- Inline SVG so we can animate the actual `stroke-dashoffset`
             and "draw" the check tick / minus instead of just scaling
             a glyph. Always mounted — the parent's `--checked` /
             `--indeterminate` classes drive opacity + dashoffset so
             the transition actually has a "from" state to ease out of.
             We mount BOTH the polyline and the line and toggle which
             one is visible with their own classes — swapping
             elements via `v-if` would reset the dashoffset and kill
             the animation. -->
        <svg
          class="r-checkbox__icon"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="3"
          stroke-linecap="round"
          stroke-linejoin="round"
        >
          <polyline
            points="5,12 10,17 19,7"
            class="r-checkbox__path r-checkbox__path--check"
          />
          <line
            x1="6"
            y1="12"
            x2="18"
            y2="12"
            class="r-checkbox__path r-checkbox__path--minus"
          />
        </svg>
        <!-- Multi-state glyph — a custom mdi icon for an icon-bearing
             state, overlaid on the box centre. Keyed by icon so swapping
             states re-pops it with the same spring the check tick uses. -->
        <RIcon
          v-if="multiIcon"
          :key="multiIcon"
          :icon="multiIcon"
          :size="multiIconSize"
          class="r-checkbox__glyph-icon"
        />
      </span>
      <span v-if="hasLabel" class="r-checkbox__body">
        <span v-if="label || slots.default" class="r-checkbox__label">
          <slot>{{ label }}</slot>
        </span>
        <span v-if="hasSubtitle" class="r-checkbox__subtitle">
          <slot name="subtitle">{{ subtitle }}</slot>
        </span>
      </span>
    </label>

    <div v-if="showDetailsRow" class="r-checkbox__details">
      <span v-for="(m, i) in messages" :key="i" class="r-checkbox__message">
        {{ m }}
      </span>
    </div>
  </div>
</template>

<style scoped>
/* ── Sizing tokens (per-size CSS vars) ─────────────────────────── */
.r-checkbox-wrap {
  display: inline-flex;
  flex-direction: column;
  gap: 2px;
  /* md defaults */
  --r-cb-box: 18px;
  --r-cb-icon: 14px;
  --r-cb-radius: 4px;
  --r-cb-border: 1.5px;
  --r-cb-color: var(--r-color-brand-primary);
}

.r-checkbox--size-xs {
  --r-cb-box: 12px;
  --r-cb-icon: 10px;
  --r-cb-radius: 3px;
  --r-cb-border: 1.25px;
}
.r-checkbox--size-sm {
  --r-cb-box: 16px;
  --r-cb-icon: 12px;
  --r-cb-radius: 3px;
}
.r-checkbox--size-md {
  --r-cb-box: 18px;
  --r-cb-icon: 14px;
  --r-cb-radius: 4px;
}
.r-checkbox--size-lg {
  --r-cb-box: 22px;
  --r-cb-icon: 16px;
  --r-cb-radius: 5px;
  --r-cb-border: 2px;
}

/* Shape — overrides the size's default radius. */
.r-checkbox--shape-rounded {
  --r-cb-radius: 8px;
}
.r-checkbox--shape-circle {
  --r-cb-radius: 50%;
}

/* ── Label wrap — clickable region ───────────────────────────── */
.r-checkbox {
  display: inline-flex;
  align-items: center;
  /* Real gap between visible box and label — no tap-area illusion. */
  gap: 10px;
  cursor: pointer;
  user-select: none;
  /* Slight vertical breathing room so a row of checkboxes is
     touch-comfortable even without extra padding from the consumer. */
  padding: 4px 0;
}

/* Bare mode — used when the consumer (overlay chrome on a GameCard,
   tight column on a list row) owns the surrounding padding. Drop the
   row breathing room and the box↔label gap so the box can be sized
   pixel-exact at the parent. The label / subtitle still render when
   supplied; the gap returns naturally when a sibling appears. */
.r-checkbox--bare .r-checkbox {
  padding: 0;
  gap: 0;
}
.r-checkbox--bare.r-checkbox--has-subtitle .r-checkbox,
.r-checkbox--bare .r-checkbox:has(.r-checkbox__body) {
  /* Restore the gap whenever body content actually renders so the
     box doesn't kiss the label. */
  gap: 10px;
}
.r-checkbox--disabled .r-checkbox {
  cursor: not-allowed;
}

/* Touch / pad hit-area — the label row is the click target by design (no
   ghost area around the box). Its natural height (box + 4px padding) sits
   under a comfortable finger target, so on touch and pad grow the row to
   --r-touch-target; the box keeps its size and stays centred. Bare mode is
   excluded — the consumer owns that chrome. */
html[data-input="touch"] .r-checkbox-wrap:not(.r-checkbox--bare) .r-checkbox,
html[data-input="pad"] .r-checkbox-wrap:not(.r-checkbox--bare) .r-checkbox {
  min-height: var(--r-touch-target);
}

/* ── Native input — visually hidden, keyboard-reachable ──────── */
.r-checkbox__input {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

/* ── Visible box ─────────────────────────────────────────────── */
.r-checkbox__box {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: var(--r-cb-box);
  height: var(--r-cb-box);
  flex-shrink: 0;
  border: var(--r-cb-border) solid var(--r-color-border-strong);
  border-radius: var(--r-cb-radius);
  background: transparent;
  /* `transform` springs back from the press-squash via the same
     overshoot easing the icon uses. `box-shadow` carries the hover
     halo and the checked-state glow. */
  transition:
    background var(--r-motion-fast) var(--r-motion-ease-out),
    border-color var(--r-motion-fast) var(--r-motion-ease-out),
    box-shadow var(--r-motion-base) var(--r-motion-ease-out),
    transform 240ms cubic-bezier(0.34, 1.56, 0.64, 1);
}

/* Hover — border darkens, faint fill, soft currentColor halo around
   the box so the user feels the affordance at a glance (same idiom
   RBtn / RSwitch use). */
.r-checkbox:hover:not(.r-checkbox--disabled) .r-checkbox__box {
  border-color: var(--r-color-fg-secondary);
  background: var(--r-color-surface-hover);
  box-shadow: 0 0 0 4px color-mix(in srgb, currentColor 10%, transparent);
}

/* Press squash — momentarily shrink the box on click. The shorter
   transition lets the squash feel crisp on press-down; releasing the
   click lets the longer spring above bounce it back. */
.r-checkbox:active:not(.r-checkbox--disabled) .r-checkbox__box {
  transform: scale(0.88);
  transition: transform 110ms var(--r-motion-ease-out);
}

/* Checked / indeterminate — solid colour fill + outer glow + inner
   top highlight. The glow extends past the box edges so a checked
   box "pops" off the page (RSwitch's on-track glow vocabulary). The
   inset highlight gives the fill a touch of dimensionality without
   committing to skeuomorphism. */
.r-checkbox--checked .r-checkbox__box,
.r-checkbox--indeterminate .r-checkbox__box,
.r-checkbox--multi-active .r-checkbox__box {
  background: var(--r-cb-fill);
  border-color: var(--r-cb-fill);
  box-shadow:
    inset 0 1px 0 color-mix(in srgb, white 18%, transparent),
    0 0 12px color-mix(in srgb, var(--r-cb-fill) 32%, transparent);
}
.r-checkbox--checked:not(.r-checkbox--disabled):hover .r-checkbox__box,
.r-checkbox--indeterminate:not(.r-checkbox--disabled):hover .r-checkbox__box,
.r-checkbox--multi-active:not(.r-checkbox--disabled):hover .r-checkbox__box {
  background: color-mix(in srgb, var(--r-cb-fill) 88%, white);
  border-color: color-mix(in srgb, var(--r-cb-fill) 88%, white);
  box-shadow:
    inset 0 1px 0 color-mix(in srgb, white 22%, transparent),
    0 0 16px color-mix(in srgb, var(--r-cb-fill) 40%, transparent);
}

/* ── Glyph (check / minus) — drawn-in stroke ──────────────────── */
/* SVG icon — sized to the per-size --r-cb-icon var, color inherits
   white from the box. Always mounted (so the path animations have a
   "from" state). A scale + opacity pop wraps the per-path draw. */
.r-checkbox__icon {
  width: var(--r-cb-icon);
  height: var(--r-cb-icon);
  color: white;
  pointer-events: none;
  transform: scale(0.6);
  opacity: 0;
  transition:
    transform 240ms cubic-bezier(0.34, 1.56, 0.64, 1),
    opacity 120ms var(--r-motion-ease-out);
}
.r-checkbox--checked .r-checkbox__icon,
.r-checkbox--indeterminate .r-checkbox__icon,
.r-checkbox--multi-check .r-checkbox__icon {
  transform: scale(1);
  opacity: 1;
}

/* Multi-state custom glyph — pinned to the box centre (RIcon is a fixed
   font-size square, so it must be translate-centred, not `inset:0`),
   hidden until an icon-bearing state pops it in with the tick's spring. */
.r-checkbox__glyph-icon {
  position: absolute;
  top: 50%;
  left: 50%;
  color: white;
  pointer-events: none;
  transform: translate(-50%, -50%) scale(0.6);
  opacity: 0;
  transition:
    transform 240ms cubic-bezier(0.34, 1.56, 0.64, 1),
    opacity 120ms var(--r-motion-ease-out);
}
.r-checkbox--multi-icon .r-checkbox__glyph-icon {
  transform: translate(-50%, -50%) scale(1);
  opacity: 1;
}

/* Both paths exist in the DOM all the time; we toggle which one is
   visible with opacity so swapping check ↔ minus doesn't unmount the
   element (which would reset stroke-dashoffset and kill the draw).
   Default: hidden (opacity 0 + stroke fully offset). */
.r-checkbox__path {
  opacity: 0;
  transition:
    stroke-dashoffset 240ms cubic-bezier(0.65, 0, 0.35, 1) 80ms,
    opacity 0ms linear 0ms;
}
/* Check polyline (5,12)→(10,17)→(19,7) ≈ 20.5 units of length. */
.r-checkbox__path--check {
  stroke-dasharray: 22;
  stroke-dashoffset: 22;
}
/* Minus (6,12)→(18,12) = 12 units of length. */
.r-checkbox__path--minus {
  stroke-dasharray: 14;
  stroke-dashoffset: 14;
}
/* Reveal the right glyph and animate its dashoffset to 0 ("draw"). */
.r-checkbox--checked:not(.r-checkbox--indeterminate) .r-checkbox__path--check,
.r-checkbox--multi-check .r-checkbox__path--check {
  opacity: 1;
  stroke-dashoffset: 0;
}
.r-checkbox--indeterminate .r-checkbox__path--minus {
  opacity: 1;
  stroke-dashoffset: 0;
}

/* ── Body (label + subtitle) ─────────────────────────────────── */
.r-checkbox__body {
  display: inline-flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.r-checkbox__label {
  font-size: var(--r-font-size-md);
  color: var(--r-color-fg-secondary);
  line-height: 1.4;
}
.r-checkbox__subtitle {
  font-size: var(--r-font-size-xs);
  color: var(--r-color-fg-muted);
  line-height: 1.4;
}
.r-checkbox--size-xs .r-checkbox__label,
.r-checkbox--size-sm .r-checkbox__label {
  font-size: var(--r-font-size-sm);
}
.r-checkbox--size-lg .r-checkbox__label {
  font-size: var(--r-font-size-lg);
}

/* When a subtitle is present the row reads as multi-line — align the
   box to the top of the body so it sits next to the label, not
   centred between label and subtitle. */
.r-checkbox--has-subtitle .r-checkbox {
  align-items: flex-start;
}
.r-checkbox--has-subtitle .r-checkbox__box {
  /* Tiny optical nudge so the box's centre lines up with the label's
     first text line, not the line-box top. */
  margin-top: 2px;
}

/* ── Disabled ────────────────────────────────────────────────── */
.r-checkbox--disabled {
  opacity: 0.45;
  pointer-events: none;
}
.r-checkbox--disabled .r-checkbox__label {
  color: var(--r-color-fg-faint);
}

/* ── Error state ─────────────────────────────────────────────── */
.r-checkbox--error .r-checkbox__box {
  border-color: var(--r-color-danger) !important;
}
.r-checkbox--error.r-checkbox--checked .r-checkbox__box,
.r-checkbox--error.r-checkbox--indeterminate .r-checkbox__box {
  background: var(--r-color-danger) !important;
}
.r-checkbox--error .r-checkbox__label,
.r-checkbox--error .r-checkbox__message {
  color: var(--r-color-danger);
}

/* ── Details row (error messages) ───────────────────────────── */
.r-checkbox__details {
  margin-top: 2px;
  font-size: var(--r-font-size-xs);
  color: var(--r-color-fg-muted);
  padding-inline-start: calc(var(--r-cb-box) + 10px);
}
.r-checkbox__message {
  display: block;
}

/* ── Focus ring — modality-gated ────────────────────────────── */
html[data-input="key"]
  .r-checkbox:has(.r-checkbox__input:focus)
  .r-checkbox__box,
html[data-input="pad"]
  .r-checkbox:has(.r-checkbox__input:focus)
  .r-checkbox__box {
  outline: 2px solid var(--r-color-focus, var(--r-cb-color));
  outline-offset: 2px;
}
html[data-input="pad"]
  .r-checkbox:has(.r-checkbox__input:focus)
  .r-checkbox__box {
  box-shadow: 0 0 0 5px color-mix(in srgb, var(--r-cb-color) 20%, transparent);
}

/* ── Variant: card — whole row clickable card ────────────────── */
.r-checkbox--variant-card .r-checkbox {
  align-items: flex-start;
  gap: 12px;
  padding: 12px 14px;
  border: 1px solid var(--r-color-border);
  border-radius: 10px;
  background: var(--r-color-bg-elevated);
  /* `transform` for the hover lift; `box-shadow` for the lift's
     drop shadow + the checked-state ring. */
  transition:
    background var(--r-motion-fast) var(--r-motion-ease-out),
    border-color var(--r-motion-fast) var(--r-motion-ease-out),
    box-shadow var(--r-motion-base) var(--r-motion-ease-out),
    transform var(--r-motion-fast) var(--r-motion-ease-out);
}
/* Hover lift — the card rises 1 px and gains a soft drop shadow so
   it reads as physical / pickable. */
.r-checkbox--variant-card:not(.r-checkbox--disabled) .r-checkbox:hover {
  background: var(--r-color-surface);
  border-color: var(--r-color-border-strong);
  transform: translateY(-1px);
  box-shadow: 0 6px 14px color-mix(in srgb, black 18%, transparent);
}
/* Press cue — settle the card back down briefly when the user
   commits the click. */
.r-checkbox--variant-card:not(.r-checkbox--disabled) .r-checkbox:active {
  transform: translateY(0);
  box-shadow: 0 2px 6px color-mix(in srgb, black 18%, transparent);
  transition:
    transform 90ms var(--r-motion-ease-out),
    box-shadow 90ms var(--r-motion-ease-out);
}
/* Checked card — brand-tinted fill + a 1 px brand ring that hugs the
   border, giving the card a "selected" outline glow. */
.r-checkbox--variant-card.r-checkbox--checked .r-checkbox {
  background: color-mix(in srgb, var(--r-cb-color) 12%, transparent);
  border-color: color-mix(in srgb, var(--r-cb-color) 60%, transparent);
  box-shadow: 0 0 0 1px color-mix(in srgb, var(--r-cb-color) 35%, transparent);
}
.r-checkbox--variant-card.r-checkbox--checked:not(.r-checkbox--disabled)
  .r-checkbox:hover {
  background: color-mix(in srgb, var(--r-cb-color) 18%, transparent);
  box-shadow:
    0 0 0 1px color-mix(in srgb, var(--r-cb-color) 50%, transparent),
    0 6px 14px color-mix(in srgb, var(--r-cb-color) 20%, transparent);
}
.r-checkbox--variant-card .r-checkbox__body {
  flex: 1 1 auto;
}
.r-checkbox--variant-card .r-checkbox__label {
  color: var(--r-color-fg);
  font-weight: var(--r-font-weight-medium);
}
.r-checkbox--variant-card.r-checkbox--checked .r-checkbox__label {
  color: var(--r-cb-color);
}

/* ── Reduced motion ───────────────────────────────────────────── */
@media (prefers-reduced-motion: reduce) {
  .r-checkbox__icon,
  .r-checkbox__glyph-icon,
  .r-checkbox__box,
  .r-checkbox--variant-card .r-checkbox {
    transition: opacity 100ms linear;
  }
  .r-checkbox__icon {
    transform: scale(1);
  }
  .r-checkbox__glyph-icon {
    transform: translate(-50%, -50%) scale(1);
  }
  /* Drop the stroke-draw — keep the glyph instantly visible so
     motion-sensitive users still see the state. */
  .r-checkbox__path {
    transition: none;
    stroke-dashoffset: 0 !important;
  }
  /* Drop the press squash and card lift — motion-sensitive users
     keep the colour swap, lose the kinetic feedback. */
  .r-checkbox:active:not(.r-checkbox--disabled) .r-checkbox__box,
  .r-checkbox--variant-card:not(.r-checkbox--disabled) .r-checkbox:hover,
  .r-checkbox--variant-card:not(.r-checkbox--disabled) .r-checkbox:active {
    transform: none;
  }
}
</style>
