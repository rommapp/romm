<script setup lang="ts">
// RTextField — wraps v-text-field with the v2 visual language.
//
// Two looks:
//   • Floating label (default, Vuetify-outlined) — used by Auth flows
//     and any place where the label needs to collapse into the field
//     when filled.
//   • Prefix label (`prefix-label` prop) — v2-native form look. A
//     slightly darker "well" sits on the LEFT of the field, separated
//     by a hairline, holding whatever you pass into `#prefix-label`
//     (icon, text, both…). The well auto-sizes to its content by
//     default; pass `label-width` for a fixed width when you need a
//     stack of fields to line up vertically.
//
// rules are typed loosely (`unknown[]`) because Vuetify's own rule
// type is structural and works for any function returning
// boolean|string.
import { computed } from "vue";
import { VTextField } from "vuetify/components/VTextField";

defineOptions({ inheritAttrs: false });

interface Props {
  modelValue?: string | number | null;
  label?: string;
  /** Placeholder text — auto-suppressed when `prefixLabel` is on so
   *  the left "well" doesn't visually duplicate. Pass it freely on
   *  the default (floating-label) variant. */
  placeholder?: string;
  type?: string;
  variant?:
    | "filled"
    | "outlined"
    | "plain"
    | "underlined"
    | "solo"
    | "solo-inverted"
    | "solo-filled";
  density?: "default" | "comfortable" | "compact";
  prependInnerIcon?: string;
  appendInnerIcon?: string;
  autocomplete?: string;
  name?: string;
  rules?: unknown[];
  hint?: string;
  hideDetails?: boolean | "auto";
  required?: boolean;
  disabled?: boolean;
  readonly?: boolean;
  loading?: boolean;
  clearable?: boolean;
  error?: boolean;
  errorMessages?: string | string[];
  /** Render a left "prefix" well inside the field instead of
   *  Vuetify's floating label. Use the `#prefix-label` slot for
   *  whatever the well should display (icon, text, both…). The well
   *  auto-sizes to its content; pass `labelWidth` when you need a
   *  fixed width to line up a stack of fields vertically. */
  prefixLabel?: boolean;
  /** Optional fixed width for the prefix-label well. When unset, the
   *  well shrinks to fit its content. Accepts any CSS length. */
  labelWidth?: string | number;
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
  rules: undefined,
  hint: undefined,
  hideDetails: false,
  errorMessages: undefined,
  prefixLabel: false,
  labelWidth: undefined,
});

defineEmits<{
  (e: "update:modelValue", value: string): void;
}>();

const labelWidthCss = computed<string | undefined>(() => {
  if (props.labelWidth === undefined) return undefined;
  return typeof props.labelWidth === "number"
    ? `${props.labelWidth}px`
    : props.labelWidth;
});

const hasFixedLabelWidth = computed(() => !!labelWidthCss.value);

// click:append-inner / click:prepend-inner are *not* declared here on
// purpose. Vuetify only makes the inner icon tabbable when a click
// listener is attached, so we let the parent's listener flow through
// `$attrs` instead of always forwarding it. That way `prepend-inner-icon`
// stays decorative (no focus ring, no tab stop) unless the parent
// genuinely subscribes — which is what you want for the password-reveal
// eye icon, but not for a plain mdi-account adornment.
</script>

<template>
  <VTextField
    v-bind="$attrs"
    class="r-text-field"
    :class="{
      'r-text-field--prefix-label': prefixLabel,
      'r-text-field--prefix-label-fixed': prefixLabel && hasFixedLabelWidth,
    }"
    :style="
      prefixLabel && labelWidthCss
        ? { '--rtf-label-w': labelWidthCss }
        : undefined
    "
    :model-value="modelValue"
    :label="prefixLabel ? undefined : label"
    :placeholder="prefixLabel ? undefined : placeholder"
    :type="type"
    :variant="variant"
    :density="density"
    :prepend-inner-icon="prefixLabel ? undefined : prependInnerIcon"
    :append-inner-icon="appendInnerIcon"
    :autocomplete="autocomplete"
    :name="name"
    :rules="rules as never"
    :hint="hint"
    :hide-details="hideDetails"
    :required="required"
    :disabled="disabled"
    :readonly="readonly"
    :loading="loading"
    :clearable="clearable"
    :error="error"
    :error-messages="errorMessages"
    @update:model-value="(v) => $emit('update:modelValue', v)"
  >
    <!-- Prefix label takes over Vuetify's prepend-inner slot when on.
         Falls back to the `label` string prop when the slot is empty. -->
    <template v-if="prefixLabel" #prepend-inner>
      <span class="r-text-field__prefix-label">
        <slot name="prefix-label">{{ label }}</slot>
      </span>
    </template>

    <!-- Pass through every consumer slot. We filter at the iterator
         level (not inside the slot body) so VTextField doesn't see a
         second `prepend-inner` registration when we own it via the
         v-if above; we also strip `#label` in prefix-label mode so it
         doesn't double-paint as Vuetify's floating label. -->
    <template
      v-for="slotName in Object.keys($slots).filter(
        (s) =>
          !(
            prefixLabel &&
            (s === 'prepend-inner' || s === 'label' || s === 'prefix-label')
          ),
      )"
      #[slotName]="slotProps"
      :key="slotName"
    >
      <slot :name="slotName" v-bind="slotProps || {}" />
    </template>
  </VTextField>
</template>

<style scoped>
/* ── Default outlined variant ─────────────────────────────────────
   Override Vuetify's 4-piece outline to a flat 1px border on
   `--r-color-border`, swapping to brand on focus and danger on error. */

.r-text-field :deep(.v-field) {
  border-radius: 8px;
  font-size: 14px;
  transition:
    background var(--r-motion-fast) var(--r-motion-ease-out),
    box-shadow var(--r-motion-fast) var(--r-motion-ease-out);
}

.r-text-field :deep(.v-field--variant-outlined) {
  background: var(--r-color-surface);
}

.r-text-field :deep(.v-field--variant-outlined .v-field__outline__start),
.r-text-field
  :deep(.v-field--variant-outlined .v-field__outline__notch::before),
.r-text-field :deep(.v-field--variant-outlined .v-field__outline__notch::after),
.r-text-field :deep(.v-field--variant-outlined .v-field__outline__end) {
  border-width: 1px;
  border-color: var(--r-color-border);
  opacity: 1;
  transition: border-color var(--r-motion-fast) var(--r-motion-ease-out);
}

.r-text-field
  :deep(.v-field--variant-outlined.v-field--focused .v-field__outline__start),
.r-text-field
  :deep(
    .v-field--variant-outlined.v-field--focused .v-field__outline__notch::before
  ),
.r-text-field
  :deep(
    .v-field--variant-outlined.v-field--focused .v-field__outline__notch::after
  ),
.r-text-field
  :deep(.v-field--variant-outlined.v-field--focused .v-field__outline__end) {
  border-color: var(--r-color-brand-primary);
}

.r-text-field :deep(.v-field--variant-outlined:hover .v-field__outline__start),
.r-text-field
  :deep(.v-field--variant-outlined:hover .v-field__outline__notch::before),
.r-text-field
  :deep(.v-field--variant-outlined:hover .v-field__outline__notch::after),
.r-text-field :deep(.v-field--variant-outlined:hover .v-field__outline__end) {
  border-color: var(--r-color-border-strong);
}

.r-text-field
  :deep(.v-field--variant-outlined.v-field--error .v-field__outline__start),
.r-text-field
  :deep(
    .v-field--variant-outlined.v-field--error .v-field__outline__notch::before
  ),
.r-text-field
  :deep(
    .v-field--variant-outlined.v-field--error .v-field__outline__notch::after
  ),
.r-text-field
  :deep(.v-field--variant-outlined.v-field--error .v-field__outline__end) {
  border-color: var(--r-color-danger);
}

/* Floating label — small + brand on focus + danger on error. */
.r-text-field :deep(.v-field-label) {
  font-size: 13px;
  font-weight: var(--r-font-weight-medium);
  color: var(--r-color-fg-muted);
  letter-spacing: 0;
}
.r-text-field :deep(.v-field--focused .v-field-label),
.r-text-field :deep(.v-field--active .v-field-label) {
  font-size: 11px;
  letter-spacing: 0.04em;
}
.r-text-field :deep(.v-field--focused .v-field-label) {
  color: var(--r-color-brand-primary);
}
.r-text-field :deep(.v-field--error .v-field-label) {
  color: var(--r-color-danger) !important;
}

/* Input value */
.r-text-field :deep(.v-field__input) {
  font-size: 14px;
  color: var(--r-color-fg);
  line-height: 1.4;
  min-height: 38px;
  padding-top: 14px;
  padding-bottom: 6px;
}
.r-text-field :deep(.v-field--variant-outlined .v-field__input) {
  padding-inline: 14px;
}

/* Inner icons */
.r-text-field :deep(.v-field__prepend-inner > .v-icon),
.r-text-field :deep(.v-field__append-inner > .v-icon) {
  color: var(--r-color-fg-muted);
  opacity: 1;
  font-size: 18px;
}
.r-text-field :deep(.v-field--focused .v-field__prepend-inner > .v-icon),
.r-text-field :deep(.v-field--focused .v-field__append-inner > .v-icon) {
  color: var(--r-color-brand-primary);
}

/* Hint / error message row */
.r-text-field :deep(.v-input__details) {
  padding-inline: 14px;
  padding-block-start: 4px;
  min-height: 18px;
}
.r-text-field :deep(.v-messages__message) {
  font-size: 11px;
  line-height: 1.4;
  color: var(--r-color-fg-muted);
}
.r-text-field :deep(.v-input--error .v-messages__message) {
  color: var(--r-color-danger);
}

.r-text-field :deep(.v-field--disabled) {
  opacity: 0.55;
}

/* ── Underlined variant — auth flows ─────────────────────────────
.r-text-field :deep(.v-field--variant-underlined) {
  background: transparent !important;
  border-radius: 0;
}

.r-text-field :deep(.v-field--variant-underlined .v-field__overlay) {
  opacity: 0 !important;
  background: transparent !important;
}
.r-text-field :deep(.v-field--variant-underlined::before) {
  border-color: var(--r-color-border-strong);
  border-bottom-width: 1px;
  transition: border-color var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-text-field
  :deep(.v-field--variant-underlined:hover:not(.v-field--focused)::before) {
  border-color: var(--r-color-fg-muted);
}
.r-text-field :deep(.v-field--variant-underlined::after) {
  border-color: var(--r-color-brand-primary);
  border-bottom-width: 2px;
}
.r-text-field :deep(.v-field--variant-underlined.v-field--error::after) {
  border-color: var(--r-color-danger);
}

.r-text-field :deep(.v-field--variant-underlined .v-field__input) {
  min-height: 52px;
}
.r-text-field :deep(.v-field--variant-underlined .v-field__field) {
  align-items: center;
}
.r-text-field :deep(.v-field--variant-underlined .v-field__prepend-inner),
.r-text-field :deep(.v-field--variant-underlined .v-field__append-inner) {
  align-items: center;
  padding-block: 0;
}
.r-text-field
  :deep(.v-field--variant-underlined .v-field-label.v-field-label--floating) {
  top: 6px;
}
.r-text-field :deep(.v-field--variant-underlined .v-field-label) {
  font-weight: var(--r-font-weight-regular);
}

/* ── Solo / filled — subtle bg, no border ──────────────────────── */

.r-text-field :deep(.v-field--variant-solo),
.r-text-field :deep(.v-field--variant-solo-filled),
.r-text-field :deep(.v-field--variant-filled) {
  background: var(--r-color-surface);
  box-shadow: none;
}
.r-text-field :deep(.v-field--variant-solo.v-field--focused),
.r-text-field :deep(.v-field--variant-solo-filled.v-field--focused),
.r-text-field :deep(.v-field--variant-filled.v-field--focused) {
  box-shadow: 0 0 0 1px
    color-mix(in srgb, var(--r-color-brand-primary) 60%, transparent);
}

/* ────────────────────────────────────────────────────────────────
   Prefix-label variant — left "well" + divider + input on the right,
   single bordered container around both. Vuetify's floating label is
   suppressed (`:label="undefined"`) and the prepend-inner slot hosts
   the `#prefix-label` slot content.

   Default: the well auto-sizes to its content (`width: auto`,
   `padding-inline: 8px`). Pass `labelWidth` to switch to a fixed-
   width well (`.r-text-field--prefix-label-fixed`) for vertical
   alignment across a stack of fields.

   `!important` on the well sizing is load-bearing — Vuetify's
   density-specific selectors otherwise outrank our scoped rules.
   ──────────────────────────────────────────────────────────────── */

.r-text-field--prefix-label :deep(.v-field) {
  background: var(--r-color-surface);
  overflow: hidden;
  border: 1px solid var(--r-color-border);
  /* Well needs to sit flush against the field's left edge — drop
     Vuetify's default field padding-left only in this mode so
     regular `prepend-inner-icon` usage keeps its breathing room. */
  padding-left: 0 !important;
}
.r-text-field--prefix-label :deep(.v-field__outline) {
  display: none;
}
.r-text-field--prefix-label:hover :deep(.v-field) {
  border-color: var(--r-color-border-strong);
}
.r-text-field--prefix-label :deep(.v-field--focused) {
  border-color: var(--r-color-brand-primary);
}
.r-text-field--prefix-label :deep(.v-field--error) {
  border-color: var(--r-color-danger);
}

/* The well — auto-sized to its content by default. */
.r-text-field--prefix-label :deep(.v-field__prepend-inner) {
  width: auto !important;
  min-width: auto !important;
  padding-block: 0 !important;
  padding-inline: 8px !important;
  align-self: stretch;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--r-color-bg-elevated);
  border-right: 1px solid var(--r-color-border);
  color: var(--r-color-fg-secondary);
}

/* Fixed-width modifier — kicks in when the caller passes
   `labelWidth`. More horizontal padding because the slot usually
   holds icon + text and we want a balanced inset. */
.r-text-field--prefix-label-fixed :deep(.v-field__prepend-inner) {
  width: var(--rtf-label-w) !important;
  min-width: var(--rtf-label-w) !important;
  padding-inline: 14px !important;
  justify-content: flex-start;
}

.r-text-field--prefix-label :deep(.v-field--focused .v-field__prepend-inner) {
  border-right-color: var(--r-color-brand-primary);
}
.r-text-field--prefix-label :deep(.v-field--error .v-field__prepend-inner) {
  border-right-color: var(--r-color-danger);
}

.r-text-field__prefix-label {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 11px;
  font-weight: var(--r-font-weight-bold);
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--r-color-fg-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.r-text-field--prefix-label
  :deep(.v-field--focused)
  .r-text-field__prefix-label {
  color: var(--r-color-brand-primary);
}
.r-text-field--prefix-label :deep(.v-field--error) .r-text-field__prefix-label {
  color: var(--r-color-danger);
}

/* Input area — auto-sized well keeps a tight left padding; the
   fixed-width variant restores the broader gap that matches the
   wider well. */
.r-text-field--prefix-label :deep(.v-field__field) {
  flex: 1;
  min-width: 0;
}
.r-text-field--prefix-label :deep(.v-field__input) {
  padding: 10px 14px;
  padding-inline-start: 10px !important;
  min-height: 38px;
}
.r-text-field--prefix-label-fixed :deep(.v-field__input) {
  padding-inline-start: 14px !important;
}

/* Append icons (clear button etc.) sit on the right inside the input
   area, no special styling needed. */
</style>
