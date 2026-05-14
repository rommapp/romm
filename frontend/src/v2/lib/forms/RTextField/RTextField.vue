<script setup lang="ts">
// RTextField — native `<input>` wrapped in a styled
// field container. Four visual variants — `outlined` (default),
// `filled`, `underlined`, `plain` — and three densities driving the
// row height via CSS vars.
//
// `prefix-label` keeps the two v2-specific label layouts working:
//
//   • "stacked" — label above the field, left-aligned, small/muted.
//     Used in dialogs and Settings forms.
//   • "inline" — label inside the field as a left "well", uppercase
//     chip-style. Used in tight popovers and menu searches.
//
// Validation is local — `rules` is a list of `(v) => true | string`
// functions; the first failing rule's message shows under the field.
// Rules run on blur and on subsequent edits (no flash on first keystroke).
// `validate()` is exposed for the future RForm to call.
//
// Loading replaces the trailing append-inner content with a spinner;
// clearable shows an × that wipes the value (focus is preserved).
import {
  computed,
  getCurrentInstance,
  nextTick,
  onMounted,
  ref,
  useAttrs,
  useSlots,
  watch,
} from "vue";
import RIcon from "../../primitives/RIcon/RIcon.vue";
import RProgressCircular from "../../primitives/RProgressCircular/RProgressCircular.vue";
import { useRFormRegistration } from "../RForm/context";

defineOptions({ inheritAttrs: false });

// `any` (not `unknown`) so call sites can write narrow signatures like
// `(v: string) => true | string` without TS rejecting on variance. The
// downside (rule callers seeing `any`) matches existing project rule
// arrays.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Rule = (value: any) => true | string;

interface Props {
  modelValue?: string | number | null;
  label?: string;
  placeholder?: string;
  type?: string;
  variant?: "outlined" | "filled" | "underlined" | "plain";
  density?: "default" | "comfortable" | "compact";
  prependInnerIcon?: string;
  appendInnerIcon?: string;
  autocomplete?: string;
  name?: string;
  rules?: Rule[];
  hint?: string;
  hideDetails?: boolean | "auto";
  required?: boolean;
  disabled?: boolean;
  readonly?: boolean;
  loading?: boolean;
  clearable?: boolean;
  autofocus?: boolean;
  error?: boolean;
  errorMessages?: string | string[];
  /** "stacked" — label above; "inline" — label as a left well. */
  prefixLabel?: "stacked" | "inline";
  /** Accent for focus + clearable hover. Defaults to brand-primary. */
  color?: string;
}

const props = withDefaults(defineProps<Props>(), {
  modelValue: undefined,
  label: undefined,
  placeholder: undefined,
  type: "text",
  variant: "outlined",
  density: "comfortable",
  prependInnerIcon: undefined,
  appendInnerIcon: undefined,
  autocomplete: undefined,
  name: undefined,
  rules: () => [],
  hint: undefined,
  hideDetails: "auto",
  required: false,
  disabled: false,
  readonly: false,
  loading: false,
  clearable: false,
  autofocus: false,
  error: false,
  errorMessages: () => [],
  prefixLabel: undefined,
  color: "primary",
});

const emit = defineEmits<{
  (e: "update:modelValue", value: string): void;
  (e: "focus", evt: FocusEvent): void;
  (e: "blur", evt: FocusEvent): void;
  (e: "clear"): void;
  /** Fired when the user clicks the prepend-inner adornment (icon or
   *  slot content). Makes the adornment behave as a button when a
   *  parent subscribes — used by password-reveal eye icons, copy
   *  buttons, etc. */
  (e: "click:prepend-inner", evt: MouseEvent): void;
  (e: "click:append-inner", evt: MouseEvent): void;
}>();

const slots = useSlots();
const attrs = useAttrs();
const inputRef = ref<HTMLInputElement | null>(null);
// Stable id for `aria-describedby` — Vue 3.5 ships `useId`, but we're
// on 3.4 still. The instance uid is unique per mounted component, which
// is plenty for aria wiring.
const fieldId = `r-tf-${getCurrentInstance()?.uid ?? Math.random().toString(36).slice(2)}`;

// ── Tone resolver — same vocabulary as the rest of the lib ─────
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

// ── Focus state ─────────────────────────────────────────────────
const focused = ref(false);
function onFocus(evt: FocusEvent) {
  focused.value = true;
  emit("focus", evt);
}
function onBlur(evt: FocusEvent) {
  focused.value = false;
  // First blur dirties the field; from then on, rules run live so the
  // user gets responsive feedback (rather than waiting for another blur).
  dirty.value = true;
  runRules();
  emit("blur", evt);
}

// ── Validation ──────────────────────────────────────────────────
const dirty = ref(false);
const internalErrors = ref<string[]>([]);

function runRules() {
  const out: string[] = [];
  for (const r of props.rules ?? []) {
    const v = r(props.modelValue);
    if (v !== true && typeof v === "string" && v.length) {
      out.push(v);
      break; // Show only the first failing rule.
    }
  }
  internalErrors.value = out;
}

/** Returns true if the field is valid right now; safe to call from RForm. */
function validate(): boolean {
  dirty.value = true;
  runRules();
  return internalErrors.value.length === 0 && !props.error;
}
function reset() {
  dirty.value = false;
  internalErrors.value = [];
}
defineExpose({ validate, reset, focus: () => inputRef.value?.focus() });

// Auto-enrol with an ancestor RForm so `form.validate()` reaches us.
// No-op when used outside a form.
useRFormRegistration({
  validate,
  reset,
  el: () => inputRef.value,
  validity: () => !hasError.value,
});

watch(
  () => props.modelValue,
  () => {
    // Once the user has touched the field once (blur), keep validating
    // on every change. Skipping while clean avoids the "errors flash
    // immediately on form mount" antipattern.
    if (dirty.value) runRules();
  },
);

// ── Derived state ───────────────────────────────────────────────
const externalMessages = computed<string[]>(() => {
  const m = props.errorMessages;
  if (Array.isArray(m)) return m;
  return m ? [m] : [];
});
const allMessages = computed<string[]>(() => [
  ...externalMessages.value,
  ...internalErrors.value,
]);
const hasError = computed(
  () =>
    props.error ||
    externalMessages.value.length > 0 ||
    internalErrors.value.length > 0,
);
const detailText = computed(() => {
  if (allMessages.value.length) return allMessages.value[0];
  if (props.hint) return props.hint;
  return "";
});
const showDetails = computed(() => {
  if (props.hideDetails === true) return false;
  if (props.hideDetails === "auto") return !!detailText.value;
  return true;
});

const hasValue = computed(
  () => props.modelValue != null && String(props.modelValue).length > 0,
);
const showClear = computed(
  () =>
    props.clearable &&
    hasValue.value &&
    !props.disabled &&
    !props.readonly &&
    !props.loading,
);
const showLoading = computed(() => !!props.loading);

function onInput(evt: Event) {
  const v = (evt.target as HTMLInputElement).value;
  emit("update:modelValue", v);
}
function clear() {
  emit("update:modelValue", "");
  emit("clear");
  // Keep focus on the input so the user can keep typing.
  nextTick(() => inputRef.value?.focus());
}

onMounted(() => {
  if (props.autofocus) inputRef.value?.focus();
});

// Slot shape helpers — drives whether to render the prepend / append
// regions at all (an empty region adds left/right padding for nothing).
const hasPrependInner = computed(
  () => !!props.prependInnerIcon || !!slots["prepend-inner"],
);
const hasAppendInner = computed(
  () =>
    !!props.appendInnerIcon ||
    !!slots["append-inner"] ||
    showClear.value ||
    showLoading.value,
);

const inlineLabelOn = computed(() => props.prefixLabel === "inline");
const stackedLabelOn = computed(() => props.prefixLabel === "stacked");

// When `label` is set without a `prefixLabel`, we don't render a
// visible label — fall back to the label as placeholder + aria-label
// so the field still reads what it's for. Consumers wanting a visible
// label pass `prefixLabel="stacked"` or `"inline"`.
const effectivePlaceholder = computed(
  () => props.placeholder ?? (!props.prefixLabel ? props.label : undefined),
);
const effectiveAriaLabel = computed(() =>
  !props.prefixLabel ? props.label : undefined,
);

// True when the parent is subscribed to a click on the adornment.
// Vue normalises `@click:append-inner` to the key `onClick:appendInner`
// in `$attrs`. The fallback handles older codepaths that camelCase the
// whole name. When subscribed, the adornment renders as a focusable
// `<button>` with hover + cursor.
function hasListener(name: string): boolean {
  const camel = `on${name[0].toUpperCase()}${name.slice(1).replace(/:(\w)/g, (_, c) => `:${c.toUpperCase()}`)}`;
  const flat = `on${name[0].toUpperCase()}${name.slice(1).replace(/:(\w)/g, (_, c) => c.toUpperCase())}`;
  return !!attrs[camel] || !!attrs[flat];
}
const prependInteractive = computed(() => hasListener("click:prepend-inner"));
const appendInteractive = computed(() => hasListener("click:append-inner"));

function onPrependInnerClick(evt: MouseEvent) {
  if (!prependInteractive.value) return;
  emit("click:prepend-inner", evt);
}
function onAppendInnerClick(evt: MouseEvent) {
  if (!appendInteractive.value) return;
  emit("click:append-inner", evt);
}
</script>

<template>
  <!-- Wrapper is a <label> when we own the visible label (stacked /
       inline) so clicking the label focuses the input. Otherwise a
       plain <div> to avoid nested labels and `label-has-for` lints. -->
  <component
    :is="prefixLabel ? 'label' : 'div'"
    v-bind="attrs"
    class="r-text-field"
    :class="[
      `r-text-field--variant-${variant}`,
      `r-text-field--density-${density}`,
      {
        'r-text-field--focused': focused,
        'r-text-field--error': hasError,
        'r-text-field--disabled': disabled,
        'r-text-field--readonly': readonly,
        'r-text-field--has-value': hasValue,
        'r-text-field--stacked': stackedLabelOn,
        'r-text-field--inline': inlineLabelOn,
      },
    ]"
    :style="{ '--r-tf-color': resolvedColor }"
  >
    <!-- Stacked label sits above the field, left-aligned. -->
    <span
      v-if="stackedLabelOn"
      class="r-text-field__label r-text-field__label--stacked"
    >
      <slot name="prefix-label">{{ label }}</slot>
    </span>

    <!-- The field box. Borders / fills / underline live here, not on
         the wrapper, so the stacked label sits *outside* the chrome. -->
    <div class="r-text-field__field">
      <!-- Inline label = a left "well" inside the field. -->
      <span
        v-if="inlineLabelOn"
        class="r-text-field__label r-text-field__label--inline"
      >
        <slot name="prefix-label">{{ label }}</slot>
      </span>

      <!-- Prepend-inner adornment (left of the input). Renders as a
           `<button>` when the parent is subscribed to
           `click:prepend-inner` so it's keyboard-reachable and shows
           a hover state; otherwise a passive `<span>`. -->
      <component
        :is="prependInteractive ? 'button' : 'span'"
        v-if="hasPrependInner && !inlineLabelOn"
        class="r-text-field__adornment r-text-field__adornment--prepend"
        :class="{ 'r-text-field__adornment--interactive': prependInteractive }"
        :type="prependInteractive ? 'button' : undefined"
        :tabindex="prependInteractive ? 0 : undefined"
        @mousedown.prevent
        @click="onPrependInnerClick"
      >
        <slot name="prepend-inner">
          <RIcon
            v-if="prependInnerIcon"
            :icon="prependInnerIcon"
            size="x-small"
          />
        </slot>
      </component>

      <input
        ref="inputRef"
        class="r-text-field__input"
        :value="modelValue ?? ''"
        :type="type"
        :placeholder="effectivePlaceholder"
        :name="name"
        :autocomplete="autocomplete"
        :disabled="disabled"
        :readonly="readonly"
        :required="required"
        :aria-label="effectiveAriaLabel"
        :aria-invalid="hasError || undefined"
        :aria-describedby="showDetails ? `${fieldId}-details` : undefined"
        @input="onInput"
        @focus="onFocus"
        @blur="onBlur"
      />

      <!-- Append-inner adornment (right of the input). Loading +
           clearable take priority over user content. Interactive when
           a parent listens to `click:append-inner`. -->
      <component
        :is="
          appendInteractive && !showLoading && !showClear ? 'button' : 'span'
        "
        v-if="hasAppendInner"
        class="r-text-field__adornment r-text-field__adornment--append"
        :class="{
          'r-text-field__adornment--interactive':
            appendInteractive && !showLoading && !showClear,
        }"
        :type="
          appendInteractive && !showLoading && !showClear ? 'button' : undefined
        "
        :tabindex="
          appendInteractive && !showLoading && !showClear ? 0 : undefined
        "
        @mousedown.prevent
        @click="onAppendInnerClick"
      >
        <RProgressCircular
          v-if="showLoading"
          :size="16"
          :width="2"
          :color="resolvedColor"
          indeterminate
        />
        <button
          v-else-if="showClear"
          type="button"
          class="r-text-field__clear"
          tabindex="-1"
          aria-label="Clear"
          @mousedown.prevent
          @click.stop="clear"
        >
          <RIcon icon="mdi-close-circle" size="x-small" />
        </button>
        <slot v-else name="append-inner">
          <RIcon
            v-if="appendInnerIcon"
            :icon="appendInnerIcon"
            size="x-small"
          />
        </slot>
      </component>

      <!-- Underline track — only painted for `underlined` variant.
           A child element rather than a border lets us animate the
           focus underline as a "draw-in from center". -->
      <span
        v-if="variant === 'underlined'"
        class="r-text-field__underline"
        aria-hidden="true"
      />
    </div>

    <!-- Details row — error message, then hint as fallback. Always
         mounted when shown so the height transition is smooth. -->
    <div
      v-if="showDetails"
      :id="`${fieldId}-details`"
      class="r-text-field__details"
      :class="{ 'r-text-field__details--error': hasError }"
    >
      <slot name="details">{{ detailText }}</slot>
    </div>
  </component>
</template>

<style scoped>
/* ── Wrapper ───────────────────────────────────────────────────── */
.r-text-field {
  display: inline-flex;
  flex-direction: column;
  gap: 4px;
  width: 100%;
  /* Density-driven field height. Padding hugs the input — adornments
     adjust per-side. */
  --r-tf-h: 40px;
  --r-tf-pad-x: 12px;
  --r-tf-radius: 8px;
  --r-tf-color: var(--r-color-brand-primary);
  color: var(--r-color-fg);
  font-family: inherit;
  /* `field-sizing: content` would let single-line shrink to content,
     but breaks placeholder visibility — stick with width: 100%. */
  text-align: left;
  /* Wrapper-level opacity transition so flipping `:disabled` eases
     instead of snapping. */
  transition: opacity var(--r-motion-med) var(--r-motion-ease-out);
}
.r-text-field--density-default {
  --r-tf-h: 48px;
  --r-tf-pad-x: 14px;
}
.r-text-field--density-comfortable {
  --r-tf-h: 40px;
  --r-tf-pad-x: 12px;
}
.r-text-field--density-compact {
  --r-tf-h: 32px;
  --r-tf-pad-x: 10px;
  --r-tf-radius: 6px;
}

/* ── Field box ─────────────────────────────────────────────────── */
.r-text-field__field {
  position: relative;
  display: inline-flex;
  align-items: center;
  width: 100%;
  height: var(--r-tf-h);
  border-radius: var(--r-tf-radius);
  background: transparent;
  border: 1px solid transparent;
  /* Slower & spring-eased so the hover halo and focus ring grow with
     a perceptible bloom instead of clipping. Background uses ease-out
     (no overshoot needed for fills); box-shadow uses the lib's spring
     curve so the halo "pops" into place. */
  transition:
    background var(--r-motion-med) var(--r-motion-ease-out),
    border-color var(--r-motion-med) var(--r-motion-ease-out),
    box-shadow var(--r-motion-med) cubic-bezier(0.34, 1.56, 0.64, 1);
}

/* ── Variants: outlined + filled (boxed) ───────────────────────── */
/* The two boxed variants share the same border + hover halo + focus
   halo vocabulary — the only difference is the resting background.
   Outlined picks the elevated bg; filled picks the warmer surface. */
.r-text-field--variant-outlined .r-text-field__field {
  border-color: var(--r-color-border);
  background: var(--r-color-bg-elevated);
}
.r-text-field--variant-filled .r-text-field__field {
  /* Borderless at rest — the warmer fill alone distinguishes it from
     outlined. Border kicks in on hover / focus, sharing the outlined
     vocabulary from there. */
  border-color: transparent;
  background: var(--r-color-surface);
}
.r-text-field--variant-outlined:not(.r-text-field--disabled):hover
  .r-text-field__field {
  border-color: var(--r-color-border-strong);
  /* Whisper-thin currentColor halo on hover — felt more than seen.
     Stays neutral (no brand) because the user hasn't committed yet. */
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--r-color-fg) 6%, transparent);
}
/* Filled hover — borderless, the whole pill lights up via a brand-tinted
   fill instead. Keeps the variant reading as a single solid element. */
.r-text-field--variant-filled:not(.r-text-field--disabled):hover
  .r-text-field__field {
  background: color-mix(
    in srgb,
    var(--r-tf-color) 8%,
    var(--r-color-surface-hover)
  );
}
/* Focused (= clicked-into, persistent) — brand-coloured border + halo
   stays for as long as the field holds focus. The `:not(...:disabled)`
   chain bumps specificity above the hover rule so brand wins when the
   user hovers a focused field. */
.r-text-field--variant-outlined.r-text-field--focused:not(
    .r-text-field--disabled
  )
  .r-text-field__field,
.r-text-field--variant-filled.r-text-field--focused:not(.r-text-field--disabled)
  .r-text-field__field {
  border-color: var(--r-tf-color);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--r-tf-color) 22%, transparent);
}
.r-text-field--variant-filled.r-text-field--focused:not(.r-text-field--disabled)
  .r-text-field__field {
  /* Slightly stronger brand tint than hover so the transition into
     focus reads as "deeper" rather than a step back. */
  background: color-mix(
    in srgb,
    var(--r-tf-color) 10%,
    var(--r-color-surface-hover)
  );
}

/* ── Variant: underlined ───────────────────────────────────────── */
.r-text-field--variant-underlined .r-text-field__field {
  border-radius: 0;
  background: transparent;
  border-bottom: 1px solid var(--r-color-border);
}
.r-text-field--variant-underlined:not(.r-text-field--disabled):hover
  .r-text-field__field {
  border-bottom-color: var(--r-color-border-strong);
}
.r-text-field__underline {
  position: absolute;
  left: 50%;
  bottom: -1px;
  width: 0;
  height: 2px;
  background: var(--r-tf-color);
  transform: translateX(-50%);
  transition: width var(--r-motion-med) cubic-bezier(0.34, 1.56, 0.64, 1);
  pointer-events: none;
}
.r-text-field--variant-underlined.r-text-field--focused
  .r-text-field__underline {
  width: 100%;
}

/* ── Variant: plain ────────────────────────────────────────────── */
.r-text-field--variant-plain .r-text-field__field {
  background: transparent;
  border-color: transparent;
}

/* ── Input ─────────────────────────────────────────────────────── */
.r-text-field__input {
  flex: 1 1 auto;
  min-width: 0;
  align-self: stretch;
  background: transparent;
  border: 0;
  outline: 0;
  padding: 0 var(--r-tf-pad-x);
  font: inherit;
  color: inherit;
  text-overflow: ellipsis;
  /* Native invalid state — kill the red glow so it doesn't fight ours. */
  box-shadow: none;
  /* Smooth padding when an adornment appears (clearable / loading
     toggle) and smooth colour fade when the field flips to disabled. */
  transition:
    padding var(--r-motion-fast) var(--r-motion-ease-out),
    color var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-text-field__input::placeholder {
  color: var(--r-color-fg-faint);
  opacity: 1;
}
.r-text-field__input:disabled {
  color: var(--r-color-fg-muted);
  -webkit-text-fill-color: var(--r-color-fg-muted);
}
.r-text-field--disabled {
  opacity: 0.55;
  cursor: not-allowed;
}
.r-text-field--disabled .r-text-field__input {
  cursor: not-allowed;
}

/* Trim inner padding when an adornment owns the side gap. */
.r-text-field__adornment + .r-text-field__input,
.r-text-field__input:has(+ .r-text-field__adornment) {
  /* Visually balance the gap with an adornment present. */
  padding-inline-start: 6px;
}
.r-text-field__field:has(.r-text-field__adornment--prepend)
  .r-text-field__input {
  padding-inline-start: 6px;
}
.r-text-field__field:has(.r-text-field__adornment--append)
  .r-text-field__input {
  padding-inline-end: 6px;
}

/* ── Adornments ────────────────────────────────────────────────── */
.r-text-field__adornment {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: var(--r-color-fg-muted);
  padding: 0 var(--r-tf-pad-x);
  flex-shrink: 0;
  /* Pull the side padding in so the icon hugs the field edge. */
  padding-inline-end: 0;
  /* Base transition so the focused/blur colour swap eases for every
     adornment, not just the interactive variant. */
  transition: color var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-text-field__adornment--append {
  padding-inline-start: 0;
  padding-inline-end: var(--r-tf-pad-x);
}
.r-text-field--focused .r-text-field__adornment {
  color: var(--r-color-fg-secondary);
}

/* Interactive adornment — button-like affordance for password-reveal
   eyes, copy buttons, dropdown chevrons, etc. */
.r-text-field__adornment--interactive {
  appearance: none;
  background: transparent;
  border: 0;
  cursor: pointer;
  font: inherit;
  transition:
    color var(--r-motion-fast) var(--r-motion-ease-out),
    transform var(--r-motion-fast) cubic-bezier(0.34, 1.56, 0.64, 1);
}
.r-text-field__adornment--interactive:hover {
  color: var(--r-tf-color);
}
.r-text-field__adornment--interactive:active {
  transform: scale(0.92);
}

/* Clearable button — its own small hover state. `tabindex=-1` keeps
   it out of the tab order; the icon shows only when there's a value. */
.r-text-field__clear {
  appearance: none;
  background: transparent;
  border: 0;
  padding: 2px;
  cursor: pointer;
  color: var(--r-color-fg-muted);
  border-radius: 50%;
  transition:
    color var(--r-motion-fast) var(--r-motion-ease-out),
    background var(--r-motion-fast) var(--r-motion-ease-out),
    transform var(--r-motion-fast) cubic-bezier(0.34, 1.56, 0.64, 1);
}
.r-text-field__clear:hover {
  color: var(--r-tf-color);
  background: color-mix(in srgb, var(--r-tf-color) 14%, transparent);
  transform: scale(1.1);
}
.r-text-field__clear:active {
  transform: scale(0.92);
}

/* ── Error state ───────────────────────────────────────────────── */
.r-text-field--error.r-text-field--variant-outlined .r-text-field__field,
.r-text-field--error.r-text-field--variant-filled .r-text-field__field {
  border-color: var(--r-color-danger) !important;
}
.r-text-field--error.r-text-field--variant-underlined .r-text-field__field {
  border-bottom-color: var(--r-color-danger);
}
.r-text-field--error.r-text-field--variant-underlined .r-text-field__underline {
  background: var(--r-color-danger);
  width: 100%;
}
.r-text-field--error.r-text-field--focused .r-text-field__field {
  box-shadow: 0 0 0 3px
    color-mix(in srgb, var(--r-color-danger) 22%, transparent);
}

/* ── Details row ───────────────────────────────────────────────── */
.r-text-field__details {
  padding-inline: 4px;
  font-size: 11px;
  line-height: 1.3;
  color: var(--r-color-fg-muted);
  min-height: 14px;
  transition: color var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-text-field__details--error {
  color: var(--r-color-danger);
}

/* ── Label — shared base ───────────────────────────────────────── */
.r-text-field__label {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--r-color-fg-muted);
  transition: color var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-text-field--focused .r-text-field__label {
  color: var(--r-tf-color);
}
.r-text-field--error .r-text-field__label {
  color: var(--r-color-danger);
}

/* ── Stacked label — sits above the field ──────────────────────── */
.r-text-field__label--stacked {
  font-size: 12px;
  font-weight: var(--r-font-weight-medium);
  line-height: 1.2;
  align-self: flex-start;
  padding-inline-start: 2px;
  margin-bottom: 4px;
}

/* ── Inline label — embedded left well ─────────────────────────── */
.r-text-field--inline .r-text-field__field {
  /* Pull the well flush to the field edge. */
  padding-inline-start: 0;
  overflow: hidden;
}
.r-text-field__label--inline {
  align-self: stretch;
  display: inline-flex;
  align-items: center;
  padding: 0 10px;
  background: var(--r-color-bg-elevated);
  border-right: 1px solid var(--r-color-border);
  font-size: 11px;
  font-weight: var(--r-font-weight-bold);
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--r-color-fg-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  transition:
    background var(--r-motion-fast) var(--r-motion-ease-out),
    border-right-color var(--r-motion-fast) var(--r-motion-ease-out),
    color var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-text-field--inline.r-text-field--focused .r-text-field__label--inline {
  border-right-color: var(--r-tf-color);
}
.r-text-field--inline.r-text-field--error .r-text-field__label--inline {
  border-right-color: var(--r-color-danger);
}
.r-text-field--inline .r-text-field__input {
  padding-inline-start: 10px;
}

/* ── Focus ring — modality-gated ───────────────────────────────── */
/* `--focused` already paints a brand-tinted halo via box-shadow (with
   the spring transition). For keyboard / gamepad users we layer a
   thin outline on top so the ring meets WCAG's "visible focus" bar
   without changing the smooth box-shadow bloom. Outline is used
   intentionally here — it doesn't transition, but it doesn't need to:
   the box-shadow halo carries the motion. */
html[data-input="key"]
  .r-text-field:has(.r-text-field__input:focus)
  .r-text-field__field,
html[data-input="pad"]
  .r-text-field:has(.r-text-field__input:focus)
  .r-text-field__field {
  outline: 2px solid var(--r-tf-color);
  outline-offset: 2px;
}

/* ── Reduced motion ───────────────────────────────────────────── */
@media (prefers-reduced-motion: reduce) {
  .r-text-field,
  .r-text-field__field,
  .r-text-field__input,
  .r-text-field__adornment,
  .r-text-field__underline,
  .r-text-field__clear,
  .r-text-field__label,
  .r-text-field__details {
    transition: none;
  }
}
</style>
