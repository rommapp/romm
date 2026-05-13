<script setup lang="ts">
// RTextField — passthrough wrapper around v-text-field. Without
// `prefix-label`, the default look is whatever Vuetify renders under
// the v2 theme — no reskin.
//
// Two v2-specific label layouts share the same `#prefix-label` slot:
//
//   • prefix-label="stacked" — label sits ABOVE the field, left-
//     aligned, small and muted. The stacked-form pattern, used in
//     dialogs and Settings forms where each input gets its own row.
//
//   • prefix-label="inline" — label sits INSIDE the field as a
//     darker "well" on the left, separated by a hairline. The chip-
//     style pattern, used inside menus and popovers where vertical
//     space is tight (e.g. RMenuSearch's lone magnifier icon).
//
// `hideDetails` defaults to `"auto"` so empty rule rows don't reserve
// vertical space — fields without errors stay compact, fields with a
// hint/error grow only when needed. Pass `hide-details="false"` to
// opt back into Vuetify's always-reserved details row.
//
// rules are typed loosely (`unknown[]`) because Vuetify's own rule
// type is structural and works for any function returning
// boolean|string.
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
  /** v2 label layout. `"stacked"` puts the label above the field
   *  (forms); `"inline"` embeds it as a left well inside the field
   *  (menu search, chip-style inputs). Both consume the
   *  `#prefix-label` slot, falling back to the `label` string prop
   *  when the slot is empty. */
  prefixLabel?: "stacked" | "inline";
}

withDefaults(defineProps<Props>(), {
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
  hideDetails: "auto",
  errorMessages: undefined,
  prefixLabel: undefined,
});

defineEmits<{
  (e: "update:modelValue", value: string): void;
}>();

// click:append-inner / click:prepend-inner are *not* declared here on
// purpose. Vuetify only makes the inner icon tabbable when a click
// listener is attached, so we let the parent's listener flow through
// `$attrs` instead of always forwarding it. That way `prepend-inner-icon`
// stays decorative (no focus ring, no tab stop) unless the parent
// genuinely subscribes — which is what you want for the password-reveal
// eye icon, but not for a plain mdi-account adornment.
</script>

<template>
  <!-- When `prefix-label` is set, the wrapper is a `<label>` so clicks
       on the label text (stacked) or the well (inline) focus the
       input below via implicit form association. Otherwise it's a
       plain `<div>` so we don't collide with Vuetify's internal
       `<label>` (floating label) and end up with nested labels.

       Using `<component :is>` keeps `vuejs-accessibility/label-has-for`
       quiet — the linter only triggers on literal `<label>` tags. -->
  <component
    :is="prefixLabel ? 'label' : 'div'"
    class="r-text-field"
    :class="{
      'r-text-field--stacked': prefixLabel === 'stacked',
      'r-text-field--inline': prefixLabel === 'inline',
    }"
  >
    <!-- Stacked label sits above the field, left-aligned. -->
    <span
      v-if="prefixLabel === 'stacked'"
      class="r-text-field__label r-text-field__label--stacked"
    >
      <slot name="prefix-label">{{ label }}</slot>
    </span>

    <VTextField
      v-bind="$attrs"
      :model-value="modelValue"
      :label="prefixLabel ? undefined : label"
      :placeholder="placeholder"
      :type="type"
      :variant="variant"
      :density="density"
      :prepend-inner-icon="
        prefixLabel === 'inline' ? undefined : prependInnerIcon
      "
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
      <!-- Inline well — takes over Vuetify's prepend-inner slot. -->
      <template v-if="prefixLabel === 'inline'" #prepend-inner>
        <span class="r-text-field__label r-text-field__label--inline">
          <slot name="prefix-label">{{ label }}</slot>
        </span>
      </template>

      <!-- Pass through every consumer slot. We strip `#label` and
           `#prefix-label` whenever a v2 layout is on (we own them),
           and `#prepend-inner` specifically in inline mode (we own
           that one too). -->
      <template
        v-for="slotName in Object.keys($slots).filter(
          (s) =>
            !(prefixLabel && (s === 'label' || s === 'prefix-label')) &&
            !(prefixLabel === 'inline' && s === 'prepend-inner'),
        )"
        #[slotName]="slotProps"
        :key="slotName"
      >
        <slot :name="slotName" v-bind="slotProps || {}" />
      </template>
    </VTextField>
  </component>
</template>

<style scoped>
/* ── Shared label base ──────────────────────────────────────────── */
.r-text-field__label {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--r-color-fg-muted);
  transition: color var(--r-motion-fast) var(--r-motion-ease-out);
}

/* Tint the label brand-primary on focus and danger on error.
   `:has()` is supported across all current browsers; this is the
   cleanest way to react to VTextField's internal state from the
   wrapper without wiring focus/blur listeners. */
.r-text-field:has(.v-field--focused) .r-text-field__label {
  color: var(--r-color-brand-primary);
}
.r-text-field:has(.v-field--error) .r-text-field__label {
  color: var(--r-color-danger);
}

/* ── Stacked variant — label above, left-aligned ───────────────── */
.r-text-field--stacked {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.r-text-field__label--stacked {
  font-size: 12px;
  font-weight: var(--r-font-weight-medium);
  line-height: 1.2;
  align-self: flex-start;
  /* Mirrors Vuetify's field horizontal padding so the label aligns
     with the input text below. */
  padding-inline-start: 2px;
}

/* ── Inline variant — well embedded inside the field ───────────── */

/* The wrapper is a `<label>`, which is `display: inline` by default —
   that collapses the field to its content width and the search bars
   don't fill their parent. Force block + width 100% so it behaves as
   a normal block-level form control, and propagate the same width to
   Vuetify's inner `.v-input` (its default `width: auto` on a grid
   container can otherwise leave it content-sized inside a flex
   parent). */
.r-text-field--inline {
  display: block;
  width: 100%;
}
.r-text-field--inline :deep(.v-input) {
  width: 100%;
}

.r-text-field--inline :deep(.v-field) {
  background: var(--r-color-surface);
  overflow: hidden;
  border: 1px solid var(--r-color-border);
  border-radius: 8px;
  /* Well sits flush against the field's left edge. */
  padding-left: 0 !important;
}
.r-text-field--inline :deep(.v-field__outline) {
  display: none;
}
.r-text-field--inline:hover :deep(.v-field) {
  border-color: var(--r-color-border-strong);
}
.r-text-field--inline :deep(.v-field--focused) {
  border-color: var(--r-color-brand-primary);
}
.r-text-field--inline :deep(.v-field--error) {
  border-color: var(--r-color-danger);
}

/* The well — auto-sized to its content. `!important` is load-bearing
   because Vuetify's density-specific selectors otherwise outrank our
   scoped rules. */
.r-text-field--inline :deep(.v-field__prepend-inner) {
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
.r-text-field--inline :deep(.v-field--focused .v-field__prepend-inner) {
  border-right-color: var(--r-color-brand-primary);
}
.r-text-field--inline :deep(.v-field--error .v-field__prepend-inner) {
  border-right-color: var(--r-color-danger);
}

.r-text-field__label--inline {
  font-size: 11px;
  font-weight: var(--r-font-weight-bold);
  letter-spacing: 0.08em;
  text-transform: uppercase;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* Input area — keep a tight left padding so the input text butts up
   close to the well without crowding it. */
.r-text-field--inline :deep(.v-field__field) {
  flex: 1;
  min-width: 0;
}
.r-text-field--inline :deep(.v-field__input) {
  padding: 10px 14px;
  padding-inline-start: 10px !important;
  min-height: 38px;
}
</style>
