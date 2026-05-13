<script setup lang="ts">
// RSelect — passthrough wrapper around v-select. Without
// `prefix-label`, the default look is whatever Vuetify renders under
// the v2 theme — no reskin on the field itself.
//
// Two v2-specific label layouts share the same `#prefix-label` slot,
// mirroring RTextField so a stack of mixed Text/Select fields aligns
// vertically:
//
//   • prefix-label="stacked" — label above the field (forms).
//   • prefix-label="inline"  — left well inside the field (chip
//     activators, menu-style inputs).
//
// `searchable` adds an RMenuSearch sticky at the top of the dropdown
// and filters items locally by the query — mirrors RMenuPanel's
// `searchable` prop so RMenu and RSelect surfaces feel identical.
//
// The dropdown (teleported outside the SFC) still gets the v2 paint
// + RMenuItem-style rows via unscoped overrides at the bottom — that
// part isn't a "reskin", it's the v2 menu surface vocabulary.
//
// `hideDetails` defaults to `"auto"` so empty rule rows don't reserve
// vertical space — fields without errors stay compact.
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
  /** v2 label layout. `"stacked"` puts the label above the field
   *  (forms); `"inline"` embeds it as a left well inside the field
   *  (chip activators, menu-style inputs). Both consume the
   *  `#prefix-label` slot, falling back to the `label` string prop
   *  when the slot is empty. */
  prefixLabel?: "stacked" | "inline";
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
  hideDetails: "auto",
  prependInnerIcon: undefined,
  appendInnerIcon: undefined,
  placeholder: undefined,
  prefixLabel: undefined,
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
  <!-- When `prefix-label` is set, the wrapper is a `<label>` so clicks
       on the label text (stacked) or the well (inline) focus the
       field below via implicit form association. Otherwise it's a
       plain `<div>` so we don't collide with Vuetify's internal
       `<label>` (floating label) and end up with nested labels.

       Using `<component :is>` keeps `vuejs-accessibility/label-has-for`
       quiet — the linter only triggers on literal `<label>` tags. -->
  <component
    :is="prefixLabel ? 'label' : 'div'"
    class="r-select"
    :class="{
      'r-select--stacked': prefixLabel === 'stacked',
      'r-select--inline': prefixLabel === 'inline',
    }"
  >
    <!-- Stacked label sits above the field, left-aligned. -->
    <span
      v-if="prefixLabel === 'stacked'"
      class="r-select__label r-select__label--stacked"
    >
      <slot name="prefix-label">{{ label }}</slot>
    </span>

    <VSelect
      v-bind="$attrs"
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
      :prepend-inner-icon="
        prefixLabel === 'inline' ? undefined : prependInnerIcon
      "
      :append-inner-icon="appendInnerIcon"
      :placeholder="placeholder"
      :chips="chips"
      :closable-chips="closableChips"
      menu-icon="mdi-chevron-down"
      :menu-props="mergedMenuProps"
      @update:model-value="(v) => $emit('update:modelValue', v)"
    >
      <!-- Inline well — takes over Vuetify's prepend-inner slot. -->
      <template v-if="prefixLabel === 'inline'" #prepend-inner>
        <span class="r-select__label r-select__label--inline">
          <slot name="prefix-label">{{ label }}</slot>
        </span>
      </template>

      <!-- Built-in search header — rendered into VSelect's
           `#prepend-item` slot so it sits at the top of the list and
           pins via `position: sticky` while items scroll. The wrapper
           div soaks pointerdown so opening the keyboard / clicking the
           input doesn't dismiss the menu the way a normal list item
           click would.

           `@keydown.stop` (and `keyup`/`keypress` for paranoia) is
           load-bearing: VSelect has a built-in typeahead — keystrokes
           bubbling up to it jump-select items as the user types.
           Stopping propagation at the wrapper keeps the input local
           to our RMenuSearch (which already updates `search`). -->
      <template v-if="searchable" #prepend-item>
        <div
          class="r-select__search"
          @mousedown.stop
          @click.stop
          @keydown.stop
          @keyup.stop
          @keypress.stop
        >
          <RMenuSearch
            :model-value="search"
            :placeholder="searchPlaceholder"
            @update:model-value="(v) => $emit('update:search', v)"
          />
        </div>
      </template>

      <!-- Pass through every consumer slot. We strip `#label` and
           `#prefix-label` whenever a v2 layout is on (we own them),
           `#prepend-inner` in inline mode (we own it too), and
           `#prepend-item` when `searchable` so it doesn't fight our
           own injection above. -->
      <template
        v-for="slotName in Object.keys($slots).filter(
          (s) =>
            !(prefixLabel && (s === 'label' || s === 'prefix-label')) &&
            !(prefixLabel === 'inline' && s === 'prepend-inner') &&
            !(searchable && s === 'prepend-item'),
        )"
        #[slotName]="slotProps"
        :key="slotName"
      >
        <slot :name="slotName" v-bind="slotProps || {}" />
      </template>
    </VSelect>
  </component>
</template>

<style scoped>
/* Outside the v2 layouts the wrapper is invisible — Vuetify paints
   the field on its own and we don't touch it. Everything below only
   applies when `prefix-label` is set. */

/* ── Shared label base ──────────────────────────────────────────── */
.r-select__label {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--r-color-fg-muted);
  transition: color var(--r-motion-fast) var(--r-motion-ease-out);
}

/* Tint the label brand-primary on focus and danger on error.
   `:has()` is supported across all current browsers; this is the
   cleanest way to react to VSelect's internal state from the wrapper
   without wiring focus/blur listeners. */
.r-select:has(.v-field--focused) .r-select__label {
  color: var(--r-color-brand-primary);
}
.r-select:has(.v-field--error) .r-select__label {
  color: var(--r-color-danger);
}

/* ── Stacked variant — label above, left-aligned ───────────────── */
.r-select--stacked {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.r-select__label--stacked {
  font-size: 12px;
  font-weight: var(--r-font-weight-medium);
  line-height: 1.2;
  align-self: flex-start;
  padding-inline-start: 2px;
}

/* ── Inline variant — well embedded inside the field ───────────── */

/* The wrapper is a `<label>`, which is `display: inline` by default —
   force block + width 100% so it behaves as a normal block-level
   control, and propagate the width to Vuetify's `.v-input` so it
   fills the wrapper even inside a flex parent. */
.r-select--inline {
  display: block;
  width: 100%;
}
.r-select--inline :deep(.v-input) {
  width: 100%;
}

.r-select--inline :deep(.v-field) {
  background: var(--r-color-surface);
  overflow: hidden;
  border: 1px solid var(--r-color-border);
  border-radius: 8px;
  /* Well sits flush against the field's left edge. */
  padding-left: 0 !important;
}
.r-select--inline :deep(.v-field__outline) {
  display: none;
}
.r-select--inline:hover :deep(.v-field) {
  border-color: var(--r-color-border-strong);
}
.r-select--inline :deep(.v-field--focused) {
  border-color: var(--r-color-brand-primary);
}
.r-select--inline :deep(.v-field--error) {
  border-color: var(--r-color-danger);
}

/* The well — auto-sized to its content. `!important` is load-bearing
   because Vuetify's density-specific selectors otherwise outrank our
   scoped rules. */
.r-select--inline :deep(.v-field__prepend-inner) {
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
.r-select--inline :deep(.v-field--focused .v-field__prepend-inner) {
  border-right-color: var(--r-color-brand-primary);
}
.r-select--inline :deep(.v-field--error .v-field__prepend-inner) {
  border-right-color: var(--r-color-danger);
}

.r-select__label--inline {
  font-size: 11px;
  font-weight: var(--r-font-weight-bold);
  letter-spacing: 0.08em;
  text-transform: uppercase;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.r-select--inline :deep(.v-field__field) {
  flex: 1;
  min-width: 0;
}
.r-select--inline :deep(.v-field__input) {
  padding: 8px 14px;
  padding-inline-start: 10px !important;
  min-height: 38px;
}
</style>

<!-- The search header lives inside `.v-overlay__content.r-select__menu`,
     teleported outside this SFC's scope. Style it unscoped so the
     layout + separator land on the rendered DOM.

     Header pinned at the top, items scroll below. We use
     `position: fixed` (not sticky) because the scroll port in
     VSelect v3 is `.v-sheet` while the search lives inside
     `.v-list` — sticky's containing-block + scroll-port lookup
     produces inconsistent results across browsers in that chain
     (confirmed empirically: computed `position: sticky` was
     applied yet the wrapper never pinned). Fixed sidesteps the
     ambiguity:

       • `.v-overlay__content.r-select__menu` already has
         `backdrop-filter: blur(28px)` set in global.css. Per CSS
         spec, an ancestor with `backdrop-filter !== none`
         establishes the containing block for descendant
         `position: fixed`. So `top: 0; left: 0; right: 0` on the
         search anchors to the panel's top, not the viewport — the
         menu can sit anywhere on screen and the search stays put
         at the menu's top edge while items scroll underneath.

       • Items render in normal flow at the top of `.v-list`, so a
         fixed search would otherwise overlap the first rows.
         We add ~58px `padding-top` to `.v-virtual-scroll__spacer`
         — that's a single offset at the very top of the scrollable
         list. As the spacer's natural height grows with virtual
         scroll, the padding stays constant, so the visible items
         are always pushed below the search.

       • `.v-list` keeps its Vuetify-default `overflow: auto` (so
         virtualisation has its scroll port to measure against)
         — we don't try to repurpose v-list as a layout shell, just
         offset its content. -->
<style>
.r-select__menu .v-list:has(.r-select__search) {
  padding-top: 0 !important;
}
.r-select__menu .r-select__search + .v-virtual-scroll__spacer {
  /* Search wrapper height (≈52px) + 6px clear gap before the
     first item. `padding-top` stays constant as the spacer's
     dynamic height (virtualisation offset) grows during scroll,
     so the gap below the fixed search is permanent.

     Adjacent-sibling selector (`+`) is load-bearing: Vuetify
     renders matching spacers both above and below the rendered
     virtualisation window. Targeting only the spacer directly
     after the search avoids padding the bottom one (which left
     an empty 58px band after the last item) and avoids the
     `:first-of-type` trap (where a sibling `.v-list__overlay`
     `<div>` made the spacer no longer "first of type"). */
  padding-top: 64px !important;
}
.r-select__menu .r-select__search {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 5;
  padding: 6px;
  /* Match the panel paint exactly — `--r-color-surface` (used
     elsewhere as a soft glass tint) is semi-transparent and lets
     scrolling items show through during scroll. The panel uses
     `--r-color-panel` for its body, so the search wrapper paints
     in the same colour to occlude rows cleanly as they scroll
     under it. Backdrop-filter mirrors the panel's glass blur so
     the wrapper reads as a continuation of the surface rather
     than a sticker pasted on top. */
  background: var(--r-color-panel);
  backdrop-filter: blur(28px);
  -webkit-backdrop-filter: blur(28px);
  border-bottom: 1px solid var(--r-color-border);
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
