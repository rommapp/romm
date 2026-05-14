<script setup lang="ts">
// RSelect — combines an RTextField-style activator (variants,
// hover/focus halos, labels) with a floating menu panel positioned by
// `@floating-ui/vue` and rendered as a teleported surface in the v2
// glass language.
//
// Single + multi-select. Items normalise via `itemTitle` / `itemValue`
// (string key or function) so any shape — strings, numbers, plain
// objects — fits without per-call-site shimming. `searchable` adds a
// sticky search input at the top of the panel.
//
// Slots `#selection` and `#item`. The `#item` slot's `props` bag is
// spread on any element you want — it carries `class` (including the
// active/selected/disabled state), `role`, `aria-*`, click/hover
// handlers, and the index data attribute. The row default is a `<li>`
// styled by `.r-select__item`.
import {
  autoUpdate,
  flip,
  offset as offsetMiddleware,
  shift,
  size as sizeMiddleware,
  useFloating,
} from "@floating-ui/vue";
import type { Placement } from "@floating-ui/vue";
import {
  computed,
  getCurrentInstance,
  nextTick,
  onBeforeUnmount,
  onMounted,
  ref,
  useAttrs,
  useSlots,
  watch,
} from "vue";
import RIcon from "../../primitives/RIcon/RIcon.vue";
import RProgressCircular from "../../primitives/RProgressCircular/RProgressCircular.vue";
import RTag from "../../primitives/RTag/RTag.vue";
import { useRFormRegistration } from "../RForm/context";
import RTextField from "../RTextField/RTextField.vue";

defineOptions({ inheritAttrs: false });

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Rule = (value: any) => true | string;

interface NormalisedItem {
  // `raw` + `value` are the consumer's source item / its key — we don't
  // know their shape but they do. Typing as `any` so `#selection` /
  // `#item` slot consumers can read fields off them without spamming
  // `as` casts.
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  raw: any;
  title: string;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  value: any;
  disabled?: boolean;
}

interface Props {
  modelValue?: unknown;
  items?: unknown[];
  label?: string;
  placeholder?: string;
  variant?: "outlined" | "filled" | "underlined" | "plain";
  density?: "default" | "comfortable" | "compact";
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  itemTitle?: string | ((item: any) => string);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  itemValue?: string | ((item: any) => unknown);
  multiple?: boolean;
  chips?: boolean;
  closableChips?: boolean;
  clearable?: boolean;
  disabled?: boolean;
  readonly?: boolean;
  loading?: boolean;
  hideDetails?: boolean | "auto";
  required?: boolean;
  prependInnerIcon?: string;
  appendInnerIcon?: string;
  rules?: Rule[];
  hint?: string;
  error?: boolean;
  errorMessages?: string | string[];
  /** "stacked" — label above; "inline" — label as a left well. */
  prefixLabel?: "stacked" | "inline";
  /** Accent for focus + selected items. Defaults to brand-primary. */
  color?: string;
  /** Adds a sticky search input at the top of the panel that filters
   *  items locally by title. */
  searchable?: boolean;
  /** v-model:search — current query string. */
  search?: string;
  searchPlaceholder?: string;
  /** Where to place the menu relative to the activator. */
  menuLocation?:
    | "bottom"
    | "top"
    | "bottom start"
    | "bottom end"
    | "top start"
    | "top end";
  /** Px gap between activator and menu. */
  menuOffset?: number;
  /** Hard cap on visible chips (defaults to ∞). Overflow is otherwise
   *  computed dynamically based on the activator's actual width. */
  maxVisibleChips?: number;
}

const props = withDefaults(defineProps<Props>(), {
  modelValue: undefined,
  items: () => [],
  label: undefined,
  placeholder: undefined,
  variant: "outlined",
  density: "comfortable",
  itemTitle: "title",
  itemValue: "value",
  multiple: false,
  chips: false,
  closableChips: false,
  clearable: false,
  disabled: false,
  readonly: false,
  loading: false,
  hideDetails: "auto",
  required: false,
  prependInnerIcon: undefined,
  appendInnerIcon: "mdi-chevron-down",
  rules: () => [],
  hint: undefined,
  error: false,
  errorMessages: () => [],
  prefixLabel: undefined,
  color: "primary",
  searchable: false,
  search: "",
  searchPlaceholder: "",
  menuLocation: "bottom",
  menuOffset: 6,
  maxVisibleChips: Number.POSITIVE_INFINITY,
});

const emit = defineEmits<{
  (e: "update:modelValue", value: unknown): void;
  (e: "update:search", value: string): void;
  (e: "focus", evt: FocusEvent): void;
  (e: "blur", evt: FocusEvent): void;
  (e: "clear"): void;
  (e: "open"): void;
  (e: "close"): void;
}>();

const slots = useSlots();
const attrs = useAttrs();

const fieldId = `r-sel-${getCurrentInstance()?.uid ?? Math.random().toString(36).slice(2)}`;

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

// ── Items normalisation ─────────────────────────────────────────
// Items can be primitives (string/number) or objects. We project each
// into `{ raw, title, value }` so the rest of the component sees a
// uniform shape. The user's `itemTitle` / `itemValue` (key or fn)
// drives the projection.
function readKey<T>(item: unknown, key: string | ((it: unknown) => T)): T {
  if (typeof key === "function") return key(item);
  if (item == null) return item as T;
  if (typeof item === "object") {
    return (item as Record<string, unknown>)[key] as T;
  }
  return item as T;
}

const normalisedItems = computed<NormalisedItem[]>(() => {
  return (props.items ?? []).map((raw) => ({
    raw,
    title: String(readKey<unknown>(raw, props.itemTitle as never) ?? ""),
    value: readKey<unknown>(raw, props.itemValue as never),
    disabled:
      typeof raw === "object" && raw != null
        ? Boolean((raw as Record<string, unknown>).disabled)
        : false,
  }));
});

const filteredItems = computed<NormalisedItem[]>(() => {
  if (!props.searchable) return normalisedItems.value;
  const q = props.search.trim().toLowerCase();
  if (!q) return normalisedItems.value;
  return normalisedItems.value.filter((it) =>
    it.title.toLowerCase().includes(q),
  );
});

// ── Selection ──────────────────────────────────────────────────
const selectedValues = computed<unknown[]>(() => {
  if (props.multiple) {
    return Array.isArray(props.modelValue) ? props.modelValue : [];
  }
  return props.modelValue === undefined || props.modelValue === null
    ? []
    : [props.modelValue];
});

function isSelected(value: unknown): boolean {
  return selectedValues.value.some((v) => v === value);
}

const selectedItems = computed<NormalisedItem[]>(() => {
  // Look up each model value against the items; preserve any value
  // that has no matching item so the activator can still render
  // "off-list" selections via the `#selection` slot.
  return selectedValues.value.map((v) => {
    const match = normalisedItems.value.find((it) => it.value === v);
    if (match) return match;
    return { raw: v, title: String(v ?? ""), value: v };
  });
});

const hasSelection = computed(() => selectedValues.value.length > 0);

// Chip overflow — keep the activator at a single line by collapsing
// chips that won't fit into a "+N" pill at the end of the row.
// The fit count is measured from a hidden mirror (`measureRef`) that
// always renders every chip; the visible row only renders the first
// `fitChipCount` of them. ResizeObserver re-measures on width changes.
const valueRef = ref<HTMLElement | null>(null);
const measureRef = ref<HTMLElement | null>(null);
const containerWidth = ref(0);
const fitChipCount = ref<number>(Number.POSITIVE_INFINITY);

const visibleChips = computed<NormalisedItem[]>(() => {
  const cap = Math.min(fitChipCount.value, props.maxVisibleChips);
  return selectedItems.value.slice(0, cap);
});
const overflowCount = computed(() =>
  Math.max(0, selectedItems.value.length - visibleChips.value.length),
);

let resizeObserver: ResizeObserver | null = null;
onMounted(() => {
  if (!valueRef.value) return;
  containerWidth.value = valueRef.value.clientWidth;
  resizeObserver = new ResizeObserver((entries) => {
    for (const e of entries) containerWidth.value = e.contentRect.width;
  });
  resizeObserver.observe(valueRef.value);
});
onBeforeUnmount(() => {
  resizeObserver?.disconnect();
  resizeObserver = null;
});

// Walk through the mirror's chips and stop when the next one (plus
// the reserved overflow-pill width) would overflow the visible row.
function recomputeFit() {
  if (!measureRef.value || containerWidth.value === 0) {
    fitChipCount.value = selectedItems.value.length;
    return;
  }
  const chips = Array.from(
    measureRef.value.querySelectorAll<HTMLElement>(
      ".r-select__chip:not(.r-select__chip--overflow)",
    ),
  );
  if (chips.length === 0) {
    // Mirror hasn't painted yet (first tick of a brand-new selection).
    // Default to showing everything until we can measure on the next
    // pass — better than rendering only the "+N" pill.
    fitChipCount.value = selectedItems.value.length;
    return;
  }
  const overflowEl = measureRef.value.querySelector<HTMLElement>(
    ".r-select__chip--overflow",
  );
  // 6 px matches `.r-select__value`'s `gap`. The overflow pill width is
  // measured from the worst-case "+N" rendered in the mirror.
  const gap = 6;
  const overflowWidth = overflowEl ? overflowEl.offsetWidth : 38;
  const available = containerWidth.value;

  let used = 0;
  let count = 0;
  for (let i = 0; i < chips.length; i++) {
    const w = chips[i].offsetWidth;
    const remaining = chips.length - 1 - i;
    const overflowReserve = remaining > 0 ? overflowWidth + gap : 0;
    const gapNow = count > 0 ? gap : 0;
    if (used + w + gapNow + overflowReserve > available) break;
    used += w + gapNow;
    count++;
  }
  // Always render at least one chip if any are selected — better to
  // clip one chip with text-overflow than to show only "+N" on its own.
  if (count === 0 && chips.length > 0) count = 1;
  fitChipCount.value = count;
}

watch(
  [selectedItems, containerWidth],
  () => {
    nextTick(recomputeFit);
  },
  { flush: "post" },
);

function selectItem(item: NormalisedItem) {
  if (item.disabled) return;
  if (props.multiple) {
    const cur = Array.isArray(props.modelValue)
      ? [...(props.modelValue as unknown[])]
      : [];
    const idx = cur.findIndex((v) => v === item.value);
    if (idx === -1) cur.push(item.value);
    else cur.splice(idx, 1);
    emit("update:modelValue", cur);
  } else {
    emit("update:modelValue", item.value);
    closeMenu();
  }
}

function removeSelection(value: unknown) {
  if (props.multiple) {
    const cur = Array.isArray(props.modelValue)
      ? (props.modelValue as unknown[]).filter((v) => v !== value)
      : [];
    emit("update:modelValue", cur);
  } else {
    clear();
  }
}

function clear() {
  emit("update:modelValue", props.multiple ? [] : null);
  emit("clear");
}

// ── Validation (mirrors RTextField) ─────────────────────────────
const dirty = ref(false);
const internalErrors = ref<string[]>([]);

function runRules() {
  const out: string[] = [];
  for (const r of props.rules ?? []) {
    const v = r(props.modelValue);
    if (v !== true && typeof v === "string" && v.length) {
      out.push(v);
      break;
    }
  }
  internalErrors.value = out;
}
function validate(): boolean {
  dirty.value = true;
  runRules();
  return internalErrors.value.length === 0 && !props.error;
}
function reset() {
  dirty.value = false;
  internalErrors.value = [];
}
defineExpose({
  validate,
  reset,
  focus: () => activatorRef.value?.focus(),
  open: openMenu,
  close: closeMenu,
});

useRFormRegistration({
  validate,
  reset,
  el: () => activatorRef.value,
  validity: () => !hasError.value,
});

watch(
  () => props.modelValue,
  () => {
    if (dirty.value) runRules();
  },
);

const externalMessages = computed<string[]>(() => {
  const m = props.errorMessages;
  if (Array.isArray(m)) return m;
  return m ? [m] : [];
});
const allMessages = computed(() => [
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

const showClear = computed(
  () =>
    props.clearable &&
    hasSelection.value &&
    !props.disabled &&
    !props.readonly &&
    !props.loading,
);

// ── Open state + floating ───────────────────────────────────────
const isOpen = ref(false);
const activatorRef = ref<HTMLElement | null>(null);
const panelRef = ref<HTMLElement | null>(null);

const PLACEMENT_MAP: Record<string, Placement> = {
  top: "top",
  bottom: "bottom",
  "top start": "top-start",
  "top end": "top-end",
  "bottom start": "bottom-start",
  "bottom end": "bottom-end",
};
const placement = computed<Placement>(
  () => PLACEMENT_MAP[props.menuLocation] ?? "bottom-start",
);

const { floatingStyles } = useFloating(activatorRef, panelRef, {
  placement,
  strategy: "fixed",
  open: isOpen,
  transform: false,
  whileElementsMounted: autoUpdate,
  middleware: computed(() => [
    offsetMiddleware(props.menuOffset),
    flip({ padding: 8 }),
    shift({ padding: 8 }),
    sizeMiddleware({
      apply({ rects, elements }) {
        // Pin the menu's min-width to the activator so single-line
        // labels and short option lists don't render as a thin chip.
        // Max height is bounded by the viewport remainder so long
        // lists scroll inside the panel.
        Object.assign(elements.floating.style, {
          minWidth: `${rects.reference.width}px`,
          maxHeight: `min(360px, var(--available-height, 360px))`,
        });
      },
      padding: 8,
    }),
  ]),
});

function openMenu() {
  if (props.disabled || props.readonly) return;
  if (isOpen.value) return;
  isOpen.value = true;
  activeIndex.value = Math.max(
    0,
    filteredItems.value.findIndex((it) => isSelected(it.value)),
  );
  emit("open");
  // RMenuSearch autofocuses on mount; keys bubble up to the panel-level
  // keydown handler. When `searchable` is off, focus stays on the
  // activator and the activator-level keydown handler steers nav.
}
function closeMenu() {
  if (!isOpen.value) return;
  isOpen.value = false;
  emit("close");
  // Run rules on close (acts as a "blur" for the field).
  dirty.value = true;
  runRules();
}
function toggleMenu() {
  if (isOpen.value) closeMenu();
  else openMenu();
}

// Click-outside — closes the panel when the user clicks anywhere
// outside both the activator and the panel.
function onDocPointerDown(evt: PointerEvent) {
  if (!isOpen.value) return;
  const target = evt.target as Node | null;
  if (!target) return;
  if (activatorRef.value?.contains(target)) return;
  if (panelRef.value?.contains(target)) return;
  closeMenu();
}
onMounted(() => {
  document.addEventListener("pointerdown", onDocPointerDown, true);
});
onBeforeUnmount(() => {
  document.removeEventListener("pointerdown", onDocPointerDown, true);
});

// Close when search is changed externally? No — keep open while
// editing search. Reset active index to 0 when filter changes so
// keyboard nav stays sensible.
watch(filteredItems, () => {
  activeIndex.value = 0;
});

// ── Keyboard nav ────────────────────────────────────────────────
const activeIndex = ref(0);

function moveActive(delta: number) {
  const list = filteredItems.value;
  if (!list.length) return;
  let i = activeIndex.value + delta;
  // Wrap + skip disabled.
  for (let n = 0; n < list.length; n++) {
    if (i < 0) i = list.length - 1;
    if (i >= list.length) i = 0;
    if (!list[i].disabled) break;
    i += delta || 1;
  }
  activeIndex.value = i;
  scrollActiveIntoView();
}
function scrollActiveIntoView() {
  nextTick(() => {
    const el = panelRef.value?.querySelector<HTMLElement>(
      `[data-r-select-index="${activeIndex.value}"]`,
    );
    el?.scrollIntoView({ block: "nearest" });
  });
}

function onActivatorKey(evt: KeyboardEvent) {
  if (props.disabled || props.readonly) return;
  switch (evt.key) {
    case "ArrowDown":
      evt.preventDefault();
      if (!isOpen.value) openMenu();
      else moveActive(1);
      break;
    case "ArrowUp":
      evt.preventDefault();
      if (!isOpen.value) openMenu();
      else moveActive(-1);
      break;
    case "Enter":
    case " ":
      if (!isOpen.value) {
        evt.preventDefault();
        openMenu();
      } else {
        evt.preventDefault();
        const item = filteredItems.value[activeIndex.value];
        if (item) selectItem(item);
      }
      break;
    case "Escape":
      if (isOpen.value) {
        evt.preventDefault();
        closeMenu();
      }
      break;
    case "Tab":
      if (isOpen.value) closeMenu();
      break;
  }
}

function onSearchKey(evt: KeyboardEvent) {
  switch (evt.key) {
    case "ArrowDown":
      evt.preventDefault();
      moveActive(1);
      break;
    case "ArrowUp":
      evt.preventDefault();
      moveActive(-1);
      break;
    case "Enter": {
      evt.preventDefault();
      const item = filteredItems.value[activeIndex.value];
      if (item) selectItem(item);
      break;
    }
    case "Escape":
      evt.preventDefault();
      closeMenu();
      activatorRef.value?.focus();
      break;
  }
}

// ── Focus tracking for the activator chrome ────────────────────
const focused = ref(false);
function onActivatorFocus(evt: FocusEvent) {
  focused.value = true;
  emit("focus", evt);
}
function onActivatorBlur(evt: FocusEvent) {
  // If focus moves into the panel (search input), keep `focused`.
  const next = evt.relatedTarget as Node | null;
  if (next && panelRef.value?.contains(next)) return;
  focused.value = false;
  emit("blur", evt);
}

// ── Label fallbacks ─────────────────────────────────────────────
const effectivePlaceholder = computed(
  () => props.placeholder ?? (!props.prefixLabel ? props.label : undefined),
);
const effectiveAriaLabel = computed(() =>
  !props.prefixLabel ? props.label : undefined,
);

const inlineLabelOn = computed(() => props.prefixLabel === "inline");
const stackedLabelOn = computed(() => props.prefixLabel === "stacked");

const hasPrependInner = computed(
  () => !!props.prependInnerIcon || !!slots["prepend-inner"],
);
</script>

<template>
  <component
    :is="prefixLabel ? 'label' : 'div'"
    v-bind="attrs"
    class="r-select"
    :class="[
      `r-select--variant-${variant}`,
      `r-select--density-${density}`,
      {
        'r-select--open': isOpen,
        'r-select--focused': focused || isOpen,
        'r-select--error': hasError,
        'r-select--disabled': disabled,
        'r-select--readonly': readonly,
        'r-select--has-value': hasSelection,
        'r-select--stacked': stackedLabelOn,
        'r-select--inline': inlineLabelOn,
        'r-select--multiple': multiple,
      },
    ]"
    :style="{ '--r-tf-color': resolvedColor }"
  >
    <span
      v-if="stackedLabelOn"
      class="r-select__label r-select__label--stacked"
    >
      <slot name="prefix-label">{{ label }}</slot>
    </span>

    <!-- Activator — a single button that opens the menu. Renders the
         current selection inside (chips or plain text). Keyboard
         navigation routes through this button. -->
    <button
      ref="activatorRef"
      type="button"
      class="r-select__field"
      :disabled="disabled"
      :aria-haspopup="'listbox'"
      :aria-expanded="isOpen"
      :aria-label="effectiveAriaLabel"
      :aria-invalid="hasError || undefined"
      :aria-describedby="showDetails ? `${fieldId}-details` : undefined"
      @click="toggleMenu"
      @keydown="onActivatorKey"
      @focus="onActivatorFocus"
      @blur="onActivatorBlur"
    >
      <span
        v-if="inlineLabelOn"
        class="r-select__label r-select__label--inline"
      >
        <slot name="prefix-label">{{ label }}</slot>
      </span>

      <span
        v-if="hasPrependInner && !inlineLabelOn"
        class="r-select__adornment r-select__adornment--prepend"
      >
        <slot name="prepend-inner">
          <RIcon
            v-if="prependInnerIcon"
            :icon="prependInnerIcon"
            size="x-small"
          />
        </slot>
      </span>

      <span ref="valueRef" class="r-select__value">
        <!-- Hidden measurement mirror — renders every selected chip
             plus a worst-case "+N" pill so we can measure widths and
             compute how many chips actually fit in `valueRef`'s
             current width. Absolutely positioned so it doesn't push
             the visible row. -->
        <span
          v-if="multiple && chips && hasSelection"
          ref="measureRef"
          class="r-select__value-mirror"
          aria-hidden="true"
        >
          <RTag
            v-for="(item, i) in selectedItems"
            :key="`mirror-${i}-${String(item.value)}`"
            class="r-select__chip"
            tone="brand"
            size="small"
            :text="item.title"
          />
          <RTag
            class="r-select__chip r-select__chip--overflow"
            tone="brand"
            size="small"
            :text="`+${selectedItems.length}`"
          />
        </span>

        <!-- Empty — show placeholder or label. -->
        <span v-if="!hasSelection" class="r-select__placeholder">
          {{ effectivePlaceholder }}
        </span>
        <!-- Multi with chips — render the visible slice as removable
             tags; anything past `maxVisibleChips` collapses into a
             "+N" pill so the activator stays single-line. -->
        <template v-else-if="multiple && chips">
          <RTag
            v-for="(item, i) in visibleChips"
            :key="`${i}-${String(item.value)}`"
            class="r-select__chip"
            tone="brand"
            size="small"
            :text="item.title"
          >
            <template v-if="closableChips" #append>
              <button
                type="button"
                class="r-select__chip-close"
                tabindex="-1"
                aria-label="Remove"
                @mousedown.prevent
                @click.stop="removeSelection(item.value)"
              >
                <RIcon icon="mdi-close" size="x-small" />
              </button>
            </template>
          </RTag>
          <RTag
            v-if="overflowCount > 0"
            class="r-select__chip r-select__chip--overflow"
            tone="brand"
            size="small"
            :text="`+${overflowCount}`"
          />
        </template>
        <!-- Single selection or multi-without-chips — defer to the
             `#selection` slot for custom rendering. Default: title. -->
        <template v-else>
          <template v-for="(item, i) in selectedItems" :key="i">
            <slot
              name="selection"
              :item="{ title: item.title, value: item.value, raw: item.raw }"
              :index="i"
            >
              <span v-if="i > 0" class="r-select__sep">,&nbsp;</span>
              <span class="r-select__title">{{ item.title }}</span>
            </slot>
          </template>
        </template>
      </span>

      <span
        class="r-select__adornment r-select__adornment--append"
        @click.stop
        @mousedown.stop
      >
        <RProgressCircular
          v-if="loading"
          :size="16"
          :width="2"
          :color="resolvedColor"
          indeterminate
        />
        <button
          v-else-if="showClear"
          type="button"
          class="r-select__clear"
          tabindex="-1"
          aria-label="Clear"
          @mousedown.prevent
          @click.stop="clear"
        >
          <RIcon icon="mdi-close-circle" size="x-small" />
        </button>
        <RIcon
          v-if="appendInnerIcon"
          :icon="appendInnerIcon"
          class="r-select__chevron"
          size="x-small"
        />
      </span>
    </button>

    <!-- Details row — error or hint. -->
    <div
      v-if="showDetails"
      :id="`${fieldId}-details`"
      class="r-select__details"
      :class="{ 'r-select__details--error': hasError }"
    >
      <slot name="details">{{ detailText }}</slot>
    </div>

    <!-- Menu panel — teleported to <body> to escape overflow / z-index
         contexts. Mounted only when open. -->
    <Teleport to="body">
      <Transition name="r-select-pop">
        <div
          v-if="isOpen"
          ref="panelRef"
          class="r-select__panel"
          :style="floatingStyles"
          role="listbox"
          :aria-multiselectable="multiple"
          @keydown="onSearchKey"
        >
          <!-- Sticky search — autofocused on open. The panel-level
               keydown handler catches Up/Down/Enter/Esc bubbling from
               whichever child is focused (search input or item rows).
               We use RTextField directly (no wrapper primitive) since
               the only extras are a magnifier icon + autofocus. -->
          <div
            v-if="searchable"
            class="r-select__search"
            @mousedown.stop
            @click.stop
          >
            <RTextField
              :model-value="search"
              :placeholder="searchPlaceholder"
              prefix-label="inline"
              hide-details
              density="compact"
              autocomplete="off"
              autofocus
              @update:model-value="
                (v) => emit('update:search', String(v ?? ''))
              "
            >
              <template #prefix-label>
                <RIcon icon="mdi-magnify" size="16" />
              </template>
            </RTextField>
          </div>

          <ul class="r-select__list">
            <li v-if="!filteredItems.length" class="r-select__empty">
              <slot name="no-data">No options</slot>
            </li>

            <slot
              v-for="(item, i) in filteredItems"
              :key="`${i}-${String(item.value)}`"
              name="item"
              :item="{ title: item.title, value: item.value, raw: item.raw }"
              :index="i"
              :active="i === activeIndex"
              :selected="isSelected(item.value)"
              :props="{
                class: [
                  'r-select__item',
                  {
                    'r-select__item--active': i === activeIndex,
                    'r-select__item--selected': isSelected(item.value),
                    'r-select__item--disabled': item.disabled,
                  },
                ],
                role: 'option',
                'aria-selected': isSelected(item.value),
                'aria-disabled': item.disabled || undefined,
                'data-r-select-index': i,
                tabindex: -1,
                onClick: () => selectItem(item),
                onMouseenter: () => (activeIndex = i),
              }"
            >
              <li
                role="option"
                class="r-select__item"
                :class="{
                  'r-select__item--active': i === activeIndex,
                  'r-select__item--selected': isSelected(item.value),
                  'r-select__item--disabled': item.disabled,
                }"
                :aria-selected="isSelected(item.value)"
                :data-r-select-index="i"
                @click="selectItem(item)"
                @mouseenter="activeIndex = i"
              >
                <span class="r-select__item-title">{{ item.title }}</span>
                <RIcon
                  v-if="isSelected(item.value)"
                  icon="mdi-check"
                  class="r-select__item-check"
                  size="x-small"
                />
              </li>
            </slot>
          </ul>
        </div>
      </Transition>
    </Teleport>
  </component>
</template>

<style scoped>
/* ── Wrapper ───────────────────────────────────────────────────── */
.r-select {
  display: inline-flex;
  flex-direction: column;
  gap: 4px;
  width: 100%;
  --r-tf-h: 40px;
  --r-tf-pad-x: 12px;
  --r-tf-radius: 8px;
  --r-tf-color: var(--r-color-brand-primary);
  color: var(--r-color-fg);
  font-family: inherit;
  text-align: left;
  transition: opacity var(--r-motion-med) var(--r-motion-ease-out);
}
.r-select--density-default {
  --r-tf-h: 48px;
  --r-tf-pad-x: 14px;
}
.r-select--density-comfortable {
  --r-tf-h: 40px;
  --r-tf-pad-x: 12px;
}
.r-select--density-compact {
  --r-tf-h: 32px;
  --r-tf-pad-x: 10px;
  --r-tf-radius: 6px;
}

/* ── Activator field — shares the RTextField chrome ────────────── */
.r-select__field {
  appearance: none;
  display: inline-flex;
  align-items: center;
  width: 100%;
  height: var(--r-tf-h);
  border-radius: var(--r-tf-radius);
  background: transparent;
  border: 1px solid transparent;
  font: inherit;
  color: inherit;
  cursor: pointer;
  outline: 0;
  padding: 0;
  text-align: left;
  transition:
    background var(--r-motion-med) var(--r-motion-ease-out),
    border-color var(--r-motion-med) var(--r-motion-ease-out),
    box-shadow var(--r-motion-med) cubic-bezier(0.34, 1.56, 0.64, 1);
}

/* Variants — mirror RTextField exactly. */
.r-select--variant-outlined .r-select__field {
  border-color: var(--r-color-border);
  background: var(--r-color-bg-elevated);
}
.r-select--variant-filled .r-select__field {
  border-color: transparent;
  background: var(--r-color-surface);
}

.r-select--variant-outlined:not(.r-select--disabled):hover .r-select__field {
  border-color: var(--r-color-border-strong);
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--r-color-fg) 6%, transparent);
}
.r-select--variant-filled:not(.r-select--disabled):hover .r-select__field {
  background: color-mix(
    in srgb,
    var(--r-tf-color) 8%,
    var(--r-color-surface-hover)
  );
}

.r-select--variant-outlined.r-select--focused:not(.r-select--disabled)
  .r-select__field,
.r-select--variant-filled.r-select--focused:not(.r-select--disabled)
  .r-select__field {
  border-color: var(--r-tf-color);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--r-tf-color) 22%, transparent);
}
.r-select--variant-filled.r-select--focused:not(.r-select--disabled)
  .r-select__field {
  background: color-mix(
    in srgb,
    var(--r-tf-color) 10%,
    var(--r-color-surface-hover)
  );
}

.r-select--variant-underlined .r-select__field {
  border-radius: 0;
  background: transparent;
  border-bottom: 1px solid var(--r-color-border);
}
.r-select--variant-underlined:not(.r-select--disabled):hover .r-select__field {
  border-bottom-color: var(--r-color-border-strong);
}
.r-select--variant-underlined.r-select--focused:not(.r-select--disabled)
  .r-select__field {
  border-bottom-color: var(--r-tf-color);
  border-bottom-width: 2px;
  margin-bottom: -1px;
}

.r-select--variant-plain .r-select__field {
  background: transparent;
  border-color: transparent;
}

/* ── Value area ────────────────────────────────────────────────── */
.r-select__value {
  position: relative;
  flex: 1 1 auto;
  min-width: 0;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  /* Single-line — overflow chips are handled by the explicit "+N" pill
     rather than wrapping. Keeps the activator height stable regardless
     of selection count. */
  flex-wrap: nowrap;
  padding: 0 var(--r-tf-pad-x);
  overflow: hidden;
}

/* Hidden measurement mirror — renders every chip + a worst-case "+N"
   pill so JS can measure how many actually fit. `visibility: hidden`
   keeps the layout sized so `offsetWidth` is accurate; `position:
   absolute` keeps it out of the visible row's flex flow. */
.r-select__value-mirror {
  position: absolute;
  visibility: hidden;
  pointer-events: none;
  top: 0;
  left: 0;
  display: inline-flex;
  gap: 6px;
  white-space: nowrap;
}
.r-select__title,
.r-select__placeholder {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.r-select__placeholder {
  color: var(--r-color-fg-faint);
}

/* When an adornment is present on either side, trim the inner gap so
   the value text sits close to the adornment. */
.r-select__field:has(.r-select__adornment--prepend) .r-select__value {
  padding-inline-start: 6px;
}
.r-select__field:has(.r-select__adornment--append) .r-select__value {
  padding-inline-end: 6px;
}

/* Chips inside multi-select — wrap rows when stacked. */
.r-select__chip {
  flex-shrink: 0;
}
.r-select__chip-close {
  appearance: none;
  border: 0;
  background: transparent;
  color: inherit;
  cursor: pointer;
  padding: 0 0 0 2px;
  display: inline-flex;
  align-items: center;
}

/* ── Adornments ────────────────────────────────────────────────── */
.r-select__adornment {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: var(--r-color-fg-muted);
  padding: 0 var(--r-tf-pad-x);
  padding-inline-end: 0;
  flex-shrink: 0;
  transition: color var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-select__adornment--append {
  padding-inline-start: 0;
  padding-inline-end: var(--r-tf-pad-x);
  gap: 4px;
}
.r-select--focused .r-select__adornment {
  color: var(--r-color-fg-secondary);
}

/* Chevron rotates when open. */
.r-select__chevron {
  transition: transform var(--r-motion-med) cubic-bezier(0.34, 1.56, 0.64, 1);
}
.r-select--open .r-select__chevron {
  transform: rotate(180deg);
  color: var(--r-tf-color);
}

.r-select__clear {
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
.r-select__clear:hover {
  color: var(--r-tf-color);
  transform: scale(1.2);
}
.r-select__clear:active {
  transform: scale(0.92);
}

/* ── Error state ───────────────────────────────────────────────── */
.r-select--error.r-select--variant-outlined .r-select__field,
.r-select--error.r-select--variant-filled .r-select__field {
  border-color: var(--r-color-danger) !important;
}
.r-select--error.r-select--variant-underlined .r-select__field {
  border-bottom-color: var(--r-color-danger);
}
.r-select--error.r-select--focused .r-select__field {
  box-shadow: 0 0 0 3px
    color-mix(in srgb, var(--r-color-danger) 22%, transparent);
}

/* ── Disabled ──────────────────────────────────────────────────── */
.r-select--disabled {
  opacity: 0.55;
}
.r-select--disabled .r-select__field {
  cursor: not-allowed;
}

/* ── Details ───────────────────────────────────────────────────── */
.r-select__details {
  padding-inline: 4px;
  font-size: 11px;
  line-height: 1.3;
  color: var(--r-color-fg-muted);
  min-height: 14px;
  transition: color var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-select__details--error {
  color: var(--r-color-danger);
}

/* ── Labels ────────────────────────────────────────────────────── */
.r-select__label {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--r-color-fg-muted);
  transition: color var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-select--focused .r-select__label {
  color: var(--r-tf-color);
}
.r-select--error .r-select__label {
  color: var(--r-color-danger);
}
.r-select__label--stacked {
  font-size: 12px;
  font-weight: var(--r-font-weight-medium);
  line-height: 1.2;
  align-self: flex-start;
  padding-inline-start: 2px;
}
.r-select__label--inline {
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
.r-select--inline.r-select--focused .r-select__label--inline {
  border-right-color: var(--r-tf-color);
}
.r-select--inline.r-select--error .r-select__label--inline {
  border-right-color: var(--r-color-danger);
}
.r-select--inline .r-select__field {
  padding-inline-start: 0;
  overflow: hidden;
}
.r-select--inline .r-select__value {
  padding-inline-start: 10px;
}

/* ── Focus ring (modality-gated) ───────────────────────────────── */
html[data-input="key"] .r-select__field:focus,
html[data-input="pad"] .r-select__field:focus {
  outline: 2px solid var(--r-tf-color);
  outline-offset: 2px;
}

@media (prefers-reduced-motion: reduce) {
  .r-select,
  .r-select__field,
  .r-select__adornment,
  .r-select__chevron,
  .r-select__clear,
  .r-select__label,
  .r-select__details {
    transition: none;
  }
}
</style>

<!-- Panel — teleported outside the SFC's scope. Painted with the v2
     glass language (matches RMenuPanel / RTooltip). Animation is the
     same overlay vocabulary the rest of the lib uses. -->
<style>
.r-select__panel {
  position: fixed;
  z-index: var(--r-z-menu, 2500);
  display: flex;
  flex-direction: column;
  min-width: 180px;
  max-width: 480px;
  overflow: hidden;
  background: var(--r-color-panel);
  border: 1px solid var(--r-color-panel-border);
  border-radius: 10px;
  box-shadow:
    0 12px 32px color-mix(in srgb, black 38%, transparent),
    0 2px 4px color-mix(in srgb, black 22%, transparent);
  backdrop-filter: blur(28px);
  -webkit-backdrop-filter: blur(28px);
  color: var(--r-color-fg);
  font-family: var(--r-font-family-sans);
}

.r-select__search {
  position: sticky;
  top: 0;
  z-index: 1;
  padding: 6px;
  background: var(--r-color-panel);
  backdrop-filter: blur(28px);
  -webkit-backdrop-filter: blur(28px);
  border-bottom: 1px solid var(--r-color-border);
}

.r-select__list {
  list-style: none;
  margin: 0;
  padding: 6px;
  overflow-y: auto;
  scrollbar-width: thin;
}

.r-select__empty {
  padding: 12px 14px;
  color: var(--r-color-fg-muted);
  font-size: 13px;
  text-align: center;
}

.r-select__item {
  display: flex;
  align-items: center;
  gap: 11px;
  padding: 9px 12px;
  border-radius: 9px;
  margin-bottom: 2px;
  font-size: 13px;
  font-weight: var(--r-font-weight-medium);
  color: var(--r-color-fg-secondary);
  cursor: pointer;
  transition:
    background var(--r-motion-fast) var(--r-motion-ease-out),
    color var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-select__item:last-child {
  margin-bottom: 0;
}
.r-select__item--active {
  background: var(--r-color-surface);
  color: var(--r-color-fg);
}
.r-select__item--selected {
  color: var(--r-color-brand-primary);
}
.r-select__item--disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.r-select__item-title {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
/* Column wrapper for two-row items (title + subtitle). Pair with the
   single-line `.r-select__item-title` and `.r-select__item-subtitle`
   classes inside it — the wrapper takes the flex slot the bare title
   would have used. */
.r-select__item-stack {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 1px;
}
.r-select__item-stack .r-select__item-title {
  /* Inside the stack the title is no longer the flex slot, so drop the
     `flex: 1` — let it size to its line height. */
  flex: 0 0 auto;
}
.r-select__item-subtitle {
  font-size: 11px;
  font-weight: var(--r-font-weight-medium);
  color: var(--r-color-fg-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.r-select__item-check {
  color: var(--r-color-brand-primary);
}

/* ── Open / close motion ───────────────────────────────────────── */
.r-select-pop-enter-from,
.r-select-pop-leave-to {
  opacity: 0;
  transform: translateY(-4px) scale(0.98);
}
.r-select-pop-enter-active {
  transition:
    opacity 140ms var(--r-motion-ease-out),
    transform 220ms cubic-bezier(0.34, 1.56, 0.64, 1);
  transform-origin: top center;
}
.r-select-pop-leave-active {
  transition:
    opacity 100ms var(--r-motion-ease-in),
    transform 100ms var(--r-motion-ease-in);
}

@media (prefers-reduced-motion: reduce) {
  .r-select-pop-enter-from,
  .r-select-pop-leave-to {
    transform: none;
  }
  .r-select-pop-enter-active,
  .r-select-pop-leave-active {
    transition: opacity 100ms linear;
  }
}
</style>
