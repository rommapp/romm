<script setup lang="ts">
// RSelect — wraps v-select with the v2 visual language.
//
// Two looks:
//   • Default outlined (legacy) — used in places like the language
//     picker and a handful of one-off Settings rows pre-redesign.
//   • Prefix label (`prefix-label` prop) — v2-native form look. A
//     slightly darker "well" sits on the LEFT of the field,
//     separated by a hairline, holding whatever you pass into
//     `#prefix-label`. The well auto-sizes to its content; pass
//     `label-width` for a fixed width when you need a stack of
//     fields to line up vertically.
//
// `searchable` adds an RMenuSearch sticky at the top of the
// dropdown and filters items locally by the query — mirrors
// RMenuPanel's `searchable` prop so RMenu and RSelect surfaces
// feel identical.
//
// Mirrors RTextField so a stack of mixed Text/Select fields aligns
// vertically.
import { computed } from "vue";
import { VSelect } from "vuetify/components/VSelect";
import RMenuSearch from "../../menus/RMenuSearch/RMenuSearch.vue";

defineOptions({ inheritAttrs: false });

interface Props {
  modelValue?: unknown;
  items?: unknown[];
  label?: string;
  variant?:
    | "filled"
    | "outlined"
    | "plain"
    | "underlined"
    | "solo"
    | "solo-inverted"
    | "solo-filled";
  density?: "default" | "comfortable" | "compact";
  itemTitle?: string | ((item: unknown) => string);
  itemValue?: string | ((item: unknown) => unknown);
  multiple?: boolean;
  clearable?: boolean;
  disabled?: boolean;
  readonly?: boolean;
  hideDetails?: boolean | "auto";
  prependInnerIcon?: string;
  appendInnerIcon?: string;
  placeholder?: string;
  chips?: boolean;
  closableChips?: boolean;
  /** Render a left "prefix" well inside the field instead of
   *  Vuetify's floating label. Use the `#prefix-label` slot. The
   *  well auto-sizes to its content; pass `labelWidth` to fix a
   *  width for vertical alignment across multiple fields. */
  prefixLabel?: boolean;
  /** Optional fixed width for the prefix-label well. When unset, the
   *  well shrinks to fit its content. */
  labelWidth?: string | number;
  /** Renders an RMenuSearch sticky at the top of the dropdown and
   *  filters the items by the query. Mirrors RMenuPanel's
   *  `searchable` prop so RMenu and RSelect surfaces feel identical. */
  searchable?: boolean;
  /** v-model:search — current query string. Two-way binding so the
   *  parent can drive / observe the query (e.g. clear on close). */
  search?: string;
  searchPlaceholder?: string;
  /** Forwarded to VSelect; the v2 panel `contentClass` is merged in so
   *  callers can still set `location`, `offset`, etc. without losing
   *  the panel styling. */
  menuProps?: Record<string, unknown>;
}

const props = withDefaults(defineProps<Props>(), {
  modelValue: undefined,
  items: () => [],
  label: undefined,
  variant: "outlined",
  density: "default",
  itemTitle: "title",
  itemValue: "value",
  hideDetails: false,
  prependInnerIcon: undefined,
  appendInnerIcon: undefined,
  placeholder: undefined,
  prefixLabel: false,
  labelWidth: undefined,
  searchable: false,
  search: "",
  searchPlaceholder: "",
  menuProps: () => ({}),
});

defineEmits<{
  (e: "update:modelValue", value: unknown): void;
  (e: "update:search", value: string): void;
}>();

// Items are filtered locally by `search` when `searchable` is on.
// We resolve a per-item title via `itemTitle` (string key or fn) so
// the filter respects whatever shape the caller passes in.
function readItemTitle(item: unknown): string {
  const it = props.itemTitle;
  if (typeof it === "function") return String(it(item) ?? "");
  if (item && typeof item === "object") {
    const v = (item as Record<string, unknown>)[it];
    return String(v ?? "");
  }
  return String(item ?? "");
}

const filteredItems = computed<unknown[]>(() => {
  if (!props.searchable) return props.items;
  const q = props.search.trim().toLowerCase();
  if (!q) return props.items;
  return (props.items as unknown[]).filter((item) =>
    readItemTitle(item).toLowerCase().includes(q),
  );
});

const labelWidthCss = computed<string | undefined>(() => {
  if (props.labelWidth === undefined) return undefined;
  return typeof props.labelWidth === "number"
    ? `${props.labelWidth}px`
    : props.labelWidth;
});

const hasFixedLabelWidth = computed(() => !!labelWidthCss.value);

// Always inject the panel content-class so the unscoped overlay
// styles below resolve. If the caller supplies their own
// contentClass we keep both.
const mergedMenuProps = computed(() => {
  const callerClass = props.menuProps.contentClass;
  const own = "r-select__menu";
  const contentClass = callerClass ? [own, callerClass].flat() : own;
  return { ...props.menuProps, contentClass };
});
</script>

<template>
  <VSelect
    v-bind="$attrs"
    class="r-select"
    :class="{
      'r-select--prefix-label': prefixLabel,
      'r-select--prefix-label-fixed': prefixLabel && hasFixedLabelWidth,
    }"
    :style="
      prefixLabel && labelWidthCss
        ? { '--rsel-label-w': labelWidthCss }
        : undefined
    "
    :model-value="modelValue"
    :items="filteredItems as never"
    :label="prefixLabel ? undefined : label"
    :variant="variant"
    :density="density"
    :item-title="itemTitle as never"
    :item-value="itemValue as never"
    :multiple="multiple"
    :clearable="clearable"
    :disabled="disabled"
    :readonly="readonly"
    :hide-details="hideDetails"
    :prepend-inner-icon="prefixLabel ? undefined : prependInnerIcon"
    :append-inner-icon="appendInnerIcon"
    :placeholder="prefixLabel ? undefined : placeholder"
    :chips="chips"
    :closable-chips="closableChips"
    menu-icon="mdi-chevron-down"
    :menu-props="mergedMenuProps"
    @update:model-value="(v) => $emit('update:modelValue', v)"
  >
    <!-- Prefix label takes over Vuetify's prepend-inner slot when on.
         Falls back to the `label` string prop when the slot is empty. -->
    <template v-if="prefixLabel" #prepend-inner>
      <span class="r-select__prefix-label">
        <slot name="prefix-label">{{ label }}</slot>
      </span>
    </template>

    <!-- Built-in search header — rendered into VSelect's
         `#prepend-item` slot so it sits at the top of the list and
         pins via `position: sticky` while items scroll. The wrapper
         div soaks pointerdown so opening the keyboard / clicking the
         input doesn't dismiss the menu the way a normal list item
         click would. -->
    <template v-if="searchable" #prepend-item>
      <div class="r-select__search" @mousedown.stop @click.stop>
        <RMenuSearch
          :model-value="search"
          :placeholder="searchPlaceholder"
          @update:model-value="(v) => $emit('update:search', v)"
        />
      </div>
    </template>

    <!-- Pass through every consumer slot. We filter at the iterator
         level (not inside the slot body) so VSelect doesn't see a
         second `prepend-inner` / `prepend-item` registration when we
         own one via the v-if above; we also strip `#label` in
         prefix-label mode so it doesn't double-paint as Vuetify's
         floating label. -->
    <template
      v-for="slotName in Object.keys($slots).filter(
        (s) =>
          !(
            prefixLabel &&
            (s === 'prepend-inner' || s === 'label' || s === 'prefix-label')
          ) && !(searchable && s === 'prepend-item'),
      )"
      #[slotName]="slotProps"
      :key="slotName"
    >
      <slot :name="slotName" v-bind="slotProps || {}" />
    </template>
  </VSelect>
</template>

<style scoped>
/* Glass-pill look — applied to every RSelect so all the page selects
   share aesthetics (header language picker, Overview status picker,
   Media manual picker…). Vuetify's outlined variant ships with a
   2-piece notched border (`v-field__outline`) that we hide and replace
   with one continuous pill border on the field itself. */
.r-select :deep(.v-field) {
  background: var(--r-color-surface);
  border: 1px solid var(--r-color-border-strong);
  border-radius: var(--r-radius-md);
  color: var(--r-color-fg-secondary);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  transition:
    background var(--r-motion-fast) var(--r-motion-ease-out),
    border-color var(--r-motion-fast) var(--r-motion-ease-out),
    color var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-select :deep(.v-field__outline) {
  display: none;
}
.r-select :deep(.v-field:hover) {
  background: var(--r-color-surface-hover);
  color: var(--r-color-fg);
}
.r-select :deep(.v-field--focused) {
  background: var(--r-color-surface-hover);
  border-color: var(--r-color-brand-primary);
  color: var(--r-color-fg);
}
.r-select :deep(.v-field__input),
.r-select :deep(.v-select__selection-text) {
  color: inherit;
  font-size: 12.5px;
  font-weight: var(--r-font-weight-medium);
}
.r-select :deep(.v-field__prepend-inner > .v-icon),
.r-select :deep(.v-field__append-inner > .v-icon) {
  opacity: 0.7;
  color: inherit;
}
.r-select :deep(.v-field--focused .v-field__prepend-inner > .v-icon),
.r-select :deep(.v-field--focused .v-field__append-inner > .v-icon) {
  opacity: 1;
}

/* ────────────────────────────────────────────────────────────────
   Prefix-label variant — mirrors RTextField. Auto-sized well by
   default; pass `labelWidth` to switch to a fixed-width well
   (`.r-select--prefix-label-fixed`) for vertical alignment across
   a stack of fields.
   ──────────────────────────────────────────────────────────────── */

.r-select--prefix-label :deep(.v-field) {
  background: var(--r-color-surface);
  border: 1px solid var(--r-color-border);
  border-radius: 8px;
  overflow: hidden;
  backdrop-filter: none;
  -webkit-backdrop-filter: none;
  /* Well sits flush against the field's left edge. */
  padding-left: 0 !important;
}
.r-select--prefix-label:hover :deep(.v-field) {
  border-color: var(--r-color-border-strong);
}
.r-select--prefix-label :deep(.v-field--focused) {
  border-color: var(--r-color-brand-primary);
}

/* The well — auto-sized to its content by default. */
.r-select--prefix-label :deep(.v-field__prepend-inner) {
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
   `labelWidth`. More horizontal padding for icon + text slots. */
.r-select--prefix-label-fixed :deep(.v-field__prepend-inner) {
  width: var(--rsel-label-w) !important;
  min-width: var(--rsel-label-w) !important;
  padding-inline: 14px !important;
  justify-content: flex-start;
}

.r-select--prefix-label :deep(.v-field--focused .v-field__prepend-inner) {
  border-right-color: var(--r-color-brand-primary);
}

.r-select__prefix-label {
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
.r-select--prefix-label :deep(.v-field--focused) .r-select__prefix-label {
  color: var(--r-color-brand-primary);
}

/* Input area — let it breathe inside the field. */
.r-select--prefix-label :deep(.v-field__field) {
  flex: 1;
  min-width: 0;
}
.r-select--prefix-label :deep(.v-field__input) {
  padding: 10px 14px;
  padding-inline-start: 10px !important;
  min-height: 38px;
  font-size: 14px;
  color: var(--r-color-fg);
}
.r-select--prefix-label-fixed :deep(.v-field__input) {
  padding-inline-start: 14px !important;
}
.r-select--prefix-label :deep(.v-select__selection-text) {
  font-size: 14px;
}
</style>

<!-- The search header lives inside `.v-overlay__content.r-select__menu`,
     teleported outside this SFC's scope. Style it unscoped so the
     sticky background + separator land on the rendered DOM. -->
<style>
.r-select__menu .r-select__search {
  position: sticky;
  top: 0;
  z-index: 2;
  padding: 6px 6px 8px;
  background: var(--r-color-surface);
  border-bottom: 1px solid var(--r-color-border);
  margin: -6px -6px 6px;
}
</style>

<!-- Teleport overrides — VSelect renders its menu into the
     `.v-overlay-container` outside any scoped subtree, so styles for
     it have to be unscoped. The shared panel paint
     (background + blur + border + radius + shadow) lives in
     `global.css` so RSelect's dropdown matches RMenu's popups
     pixel-for-pixel. Here we only style the inner list + rows so they
     mirror RMenuItem. -->
<style>
/* VSelect wraps its menu content in `.v-select__content > .v-sheet`,
   and `.v-sheet` paints `rgb(var(--v-theme-surface))` (= the v1 grey).
   Without nullifying it, our panel paint on `.v-overlay__content` is
   covered by the sheet and the dropdown reads as Vuetify-grey instead
   of the v2 panel. */
.r-select__menu .v-select__content,
.r-select__menu .v-sheet {
  background: transparent !important;
  box-shadow: none !important;
}

.r-select__menu .v-list {
  background: transparent !important;
  padding: 6px !important;
  color: var(--r-color-fg);
  font-family: var(--r-font-family-sans);
}

/* Vuetify paints `.v-list-item__overlay` (full-bleed cover) on
   hover/active — kill it so the rounded background we paint on the
   row itself is what shows. Same trick for the focus underlay. */
.r-select__menu .v-list-item__overlay,
.r-select__menu .v-list-item__underlay {
  display: none !important;
}

/* Items — RMenuItem visual: 9px radius, 9px 12px padding, gap 11px,
   13px medium text, surface hover. !important needed because Vuetify
   ships `.v-list-item--variant-elevated/flat` with an opaque
   `rgba(var(--v-theme-surface))` background + a default elevation —
   without nullifying both, every row paints a grey card on top of our
   glass panel and bleeds the v1 look back in. */
.r-select__menu .v-list-item {
  display: flex !important;
  align-items: center;
  gap: 11px;
  min-height: 0 !important;
  padding: 9px 12px !important;
  border-radius: 9px !important;
  margin-bottom: 2px;
  font-size: 13px !important;
  font-weight: var(--r-font-weight-medium);
  color: var(--r-color-fg-secondary);
  background: transparent !important;
  box-shadow: none !important;
  transition:
    background var(--r-motion-fast) var(--r-motion-ease-out),
    color var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-select__menu .v-list-item:last-child {
  margin-bottom: 0;
}
.r-select__menu .v-list-item:hover,
.r-select__menu .v-list-item:focus-visible,
.r-select__menu .v-list-item--active {
  background: var(--r-color-surface) !important;
  color: var(--r-color-fg) !important;
}
/* Selected option — same surface bg as hover, plus a brand-tinted
   tone so the user sees "this is the current value". */
.r-select__menu .v-list-item--active {
  color: var(--r-color-brand-primary) !important;
}
.r-select__menu .v-list-item-title {
  font-size: inherit;
  font-weight: inherit;
}
</style>
