<script setup lang="ts">
// RTextField — passthrough wrapper around v-text-field. The default
// look is whatever Vuetify renders under the v2 theme — no reskin.
//
// The only v2-specific addition is the `prefix-label` variant: a
// slightly darker "well" sits on the LEFT of the field, separated by
// a hairline, holding whatever you pass into `#prefix-label` (icon,
// text, both…). The well auto-sizes to its content by default; pass
// `label-width` for a fixed width when you need a stack of fields to
// line up vertically.
//
// Without `prefix-label`, all CSS below is inert and Vuetify's stock
// variants (outlined / underlined / solo / filled / plain) paint
// themselves from the v2-dark / v2-light theme registered in
// `theme/vuetify.ts`.
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

   Everything outside this block is left to Vuetify + the v2 theme.
   ──────────────────────────────────────────────────────────────── */

.r-text-field--prefix-label :deep(.v-field) {
  background: var(--r-color-surface);
  overflow: hidden;
  border: 1px solid var(--r-color-border);
  border-radius: 8px;
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
</style>
