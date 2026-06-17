<script setup lang="ts">
// RComboboxField — free-text multi-select with chips. Users can type
// any value (commit on Enter / blur / comma), remove chips with
// Backspace at the empty input or by clicking their close button, and
// pick from an optional `items` autocomplete dropdown of suggestions.
//
// Differs from RSelect: there's no enforced item set. `items` is
// suggestion-only — typed values that don't match are still committed.
// Used by surfaces that capture user-defined tags (companies / genres
// / franchises in the edit-ROM dialog) or curate from a known list
// without locking the input (game modes, age ratings).
//
// The autocomplete dropdown is rendered with `@floating-ui/vue` so it
// shares the same positioning vocabulary as RMenu / RSelect / RTooltip.
//
// `prefix-label` mirrors RTextField — `"stacked"` puts the label above,
// `"inline"` puts it as a left-side chip on the field. Pass-through
// `density` / `variant` / `disabled` / `placeholder` styling, plus
// `closable-chips` (default true) to drop the X button if the consumer
// wants chips to be permanent until the input is cleared.
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
  nextTick,
  onBeforeUnmount,
  onMounted,
  ref,
  useId,
  useSlots,
  watch,
} from "vue";
import RIcon from "@/v2/lib/primitives/RIcon/RIcon.vue";
import RTag from "@/v2/lib/primitives/RTag/RTag.vue";

defineOptions({ inheritAttrs: false });

interface Props {
  modelValue?: string[];
  /** Optional suggestion list. Typed values that don't match are still
   *  committed — this is autocomplete, not enforcement. */
  items?: string[];
  label?: string;
  placeholder?: string;
  /** `stacked` → label above the field. `inline` → label as a left
   *  prefix on the field. Mirrors RTextField. */
  prefixLabel?: "stacked" | "inline" | null;
  variant?: "outlined" | "filled" | "underlined" | "plain";
  density?: "default" | "comfortable" | "compact";
  hideDetails?: boolean;
  hint?: string;
  errorMessages?: string | string[];
  disabled?: boolean;
  /** Render an X button on each chip to remove it (default true). */
  closableChips?: boolean;
  /** Drop the autocomplete dropdown entirely. Pure free-text input. */
  noSuggestions?: boolean;
  /** Render a field-level X that wipes every committed chip in one
   *  click. Sits next to the input on the right edge of the field, so
   *  the affordance reads identically to RTextField's clearable. */
  clearable?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
  modelValue: () => [],
  items: () => [],
  label: undefined,
  placeholder: undefined,
  prefixLabel: null,
  variant: "outlined",
  density: "default",
  hideDetails: false,
  hint: undefined,
  errorMessages: undefined,
  disabled: false,
  closableChips: true,
  noSuggestions: false,
  clearable: false,
});

const emit = defineEmits<{
  (e: "update:modelValue", value: string[]): void;
}>();

const slots = useSlots();
void slots;

// Generate an id once so every consumer gets a stable label↔input
// association without forcing them to pass an id prop.
const inputId = useId();

// ── State ──────────────────────────────────────────────────────
const inputRef = ref<HTMLInputElement | null>(null);
const fieldRef = ref<HTMLElement | null>(null);
const panelRef = ref<HTMLElement | null>(null);
const query = ref("");
const isOpen = ref(false);
const activeIndex = ref(-1);

// Wrap the controlled value in a local computed so we don't mutate the
// prop array in place.
const chips = computed(() => props.modelValue);

// Suggestions = items that include the typed query AND aren't already
// committed (no point suggesting "Action" when it's already a chip).
const suggestions = computed(() => {
  if (props.noSuggestions || !props.items.length) return [];
  const q = query.value.trim().toLowerCase();
  const taken = new Set(chips.value.map((c) => c.toLowerCase()));
  return props.items.filter(
    (item) =>
      !taken.has(item.toLowerCase()) &&
      (q === "" || item.toLowerCase().includes(q)),
  );
});

const hasSuggestions = computed(() => suggestions.value.length > 0);

// ── Floating panel ─────────────────────────────────────────────
const placement: Placement = "bottom-start";
const { floatingStyles } = useFloating(fieldRef, panelRef, {
  placement,
  strategy: "fixed",
  open: isOpen,
  transform: false,
  whileElementsMounted: autoUpdate,
  middleware: [
    offsetMiddleware(4),
    flip({ padding: 8 }),
    shift({ padding: 8 }),
    sizeMiddleware({
      apply({ rects, elements, availableHeight }) {
        Object.assign(elements.floating.style, {
          minWidth: `${rects.reference.width}px`,
          maxHeight: `${Math.min(280, availableHeight - 8)}px`,
        });
      },
      padding: 8,
    }),
  ],
});

// ── Commit / remove ─────────────────────────────────────────────
function commit(raw: string) {
  const trimmed = raw.trim();
  if (!trimmed) return;
  // Allow comma-separated paste (`tag1, tag2, tag3`) — split, dedupe
  // against the current set, and commit them in one update.
  const parts = trimmed
    .split(",")
    .map((p) => p.trim())
    .filter(Boolean);
  if (!parts.length) return;
  const taken = new Set(chips.value.map((c) => c.toLowerCase()));
  const next = [...chips.value];
  for (const p of parts) {
    if (!taken.has(p.toLowerCase())) {
      next.push(p);
      taken.add(p.toLowerCase());
    }
  }
  if (next.length !== chips.value.length) {
    emit("update:modelValue", next);
  }
  query.value = "";
  activeIndex.value = -1;
}

function removeAt(index: number) {
  if (index < 0 || index >= chips.value.length) return;
  const next = chips.value.slice();
  next.splice(index, 1);
  emit("update:modelValue", next);
}

function removeLast() {
  if (!chips.value.length) return;
  removeAt(chips.value.length - 1);
}

function clearAll() {
  if (!chips.value.length && !query.value) return;
  query.value = "";
  emit("update:modelValue", []);
  nextTick(() => inputRef.value?.focus());
}

// ── Input wiring ───────────────────────────────────────────────
function openPanel() {
  if (props.disabled || props.noSuggestions) return;
  isOpen.value = true;
}

function closePanel() {
  isOpen.value = false;
  activeIndex.value = -1;
}

function onFocus() {
  openPanel();
}

function onBlur() {
  // Commit anything still typed when the user tabs away — match the
  // expected "leave the field with what you wrote" behaviour.
  if (query.value.trim()) commit(query.value);
  // Defer close so a click on a suggestion isn't swallowed.
  setTimeout(() => closePanel(), 120);
}

function onInput(e: Event) {
  query.value = (e.target as HTMLInputElement).value;
  openPanel();
  activeIndex.value = -1;
}

function onKeyDown(e: KeyboardEvent) {
  switch (e.key) {
    case "Enter": {
      e.preventDefault();
      if (activeIndex.value >= 0 && suggestions.value[activeIndex.value]) {
        commit(suggestions.value[activeIndex.value]);
      } else if (query.value.trim()) {
        commit(query.value);
      }
      break;
    }
    case ",": {
      // Comma also commits — matches the paste-friendly contract.
      e.preventDefault();
      commit(query.value);
      break;
    }
    case "Backspace": {
      if (query.value === "") removeLast();
      break;
    }
    case "ArrowDown": {
      if (!hasSuggestions.value) return;
      e.preventDefault();
      activeIndex.value = (activeIndex.value + 1) % suggestions.value.length;
      openPanel();
      break;
    }
    case "ArrowUp": {
      if (!hasSuggestions.value) return;
      e.preventDefault();
      activeIndex.value =
        activeIndex.value <= 0
          ? suggestions.value.length - 1
          : activeIndex.value - 1;
      openPanel();
      break;
    }
    case "Escape": {
      e.preventDefault();
      closePanel();
      break;
    }
  }
}

function pickSuggestion(item: string) {
  commit(item);
  nextTick(() => inputRef.value?.focus());
}

// Outside-click closes the panel — mirrors RMenu / RSelect.
function onDocPointerDown(evt: PointerEvent) {
  if (!isOpen.value) return;
  const target = evt.target as Node | null;
  if (!target) return;
  if (fieldRef.value?.contains(target as Node)) return;
  if (panelRef.value?.contains(target as Node)) return;
  closePanel();
}

onMounted(() => {
  document.addEventListener("pointerdown", onDocPointerDown, true);
});
onBeforeUnmount(() => {
  document.removeEventListener("pointerdown", onDocPointerDown, true);
});

// Reset active highlight when the suggestion set changes.
watch(suggestions, () => {
  activeIndex.value = -1;
});

// ── Layout classes ─────────────────────────────────────────────
const inlineLabelOn = computed(() => props.prefixLabel === "inline");
const stackedLabelOn = computed(() => props.prefixLabel === "stacked");

const showClear = computed(
  () =>
    props.clearable &&
    !props.disabled &&
    (chips.value.length > 0 || query.value.length > 0),
);

const errorList = computed<string[]>(() => {
  if (!props.errorMessages) return [];
  return Array.isArray(props.errorMessages)
    ? props.errorMessages
    : [props.errorMessages];
});
const hasError = computed(() => errorList.value.length > 0);
const showDetails = computed(
  () => !props.hideDetails && (hasError.value || !!props.hint),
);
</script>

<template>
  <div
    class="r-combobox-field"
    :class="[
      `r-combobox-field--variant-${variant}`,
      `r-combobox-field--density-${density}`,
      {
        'r-combobox-field--disabled': disabled,
        'r-combobox-field--error': hasError,
      },
    ]"
  >
    <!-- eslint-disable-next-line vuejs-accessibility/label-has-for -->
    <label
      v-if="stackedLabelOn && label"
      :for="inputId"
      class="r-combobox-field__label r-combobox-field__label--stacked"
    >
      {{ label }}
    </label>

    <label ref="fieldRef" :for="inputId" class="r-combobox-field__field">
      <span
        v-if="inlineLabelOn && label"
        class="r-combobox-field__label r-combobox-field__label--inline"
      >
        {{ label }}
      </span>

      <div class="r-combobox-field__chips">
        <RTag
          v-for="(chip, i) in chips"
          :key="`${i}-${chip}`"
          class="r-combobox-field__chip"
          tone="brand"
          size="small"
          :text="chip"
        >
          <template v-if="closableChips" #append>
            <button
              type="button"
              class="r-combobox-field__chip-close"
              tabindex="-1"
              aria-label="Remove"
              @mousedown.prevent
              @click.stop="removeAt(i)"
            >
              <RIcon icon="mdi-close" size="x-small" />
            </button>
          </template>
        </RTag>

        <input
          :id="inputId"
          ref="inputRef"
          v-bind="$attrs"
          type="text"
          class="r-combobox-field__input"
          :value="query"
          :placeholder="!chips.length ? placeholder : undefined"
          :disabled="disabled"
          @focus="onFocus"
          @blur="onBlur"
          @input="onInput"
          @keydown="onKeyDown"
        />
      </div>

      <!-- Field-level clearable — wipes the whole chip set at once. The
           per-chip X (`closableChips`) still removes individual chips;
           this is the "reset the field" affordance that mirrors
           RTextField's clearable. -->
      <button
        v-if="showClear"
        type="button"
        class="r-combobox-field__clear"
        tabindex="-1"
        aria-label="Clear"
        @mousedown.prevent
        @click.stop="clearAll"
      >
        <RIcon icon="mdi-close-circle" size="x-small" />
      </button>
    </label>

    <Teleport to="body">
      <Transition name="r-combobox-pop">
        <div
          v-if="isOpen && hasSuggestions"
          ref="panelRef"
          class="r-combobox-field__panel"
          :style="floatingStyles"
          role="listbox"
        >
          <!-- Listbox items — keyboard activation is handled by the
               input's ArrowDown / Enter wiring, not by per-item key
               handlers. The lint rule expects per-item keydown which
               isn't the listbox pattern. -->
          <ul class="r-combobox-field__list">
            <!-- eslint-disable-next-line vuejs-accessibility/click-events-have-key-events, vuejs-accessibility/mouse-events-have-key-events, vuejs-accessibility/interactive-supports-focus -->
            <li
              v-for="(item, i) in suggestions"
              :key="item"
              role="option"
              class="r-combobox-field__item"
              :class="{ 'r-combobox-field__item--active': i === activeIndex }"
              :aria-selected="i === activeIndex"
              @mousedown.prevent
              @mouseenter="activeIndex = i"
              @click="pickSuggestion(item)"
            >
              {{ item }}
            </li>
          </ul>
        </div>
      </Transition>
    </Teleport>

    <div
      v-if="showDetails"
      class="r-combobox-field__details"
      :class="{ 'r-combobox-field__details--error': hasError }"
    >
      <template v-if="hasError">
        {{ errorList[0] }}
      </template>
      <template v-else>
        {{ hint }}
      </template>
    </div>
  </div>
</template>

<style scoped>
.r-combobox-field {
  display: inline-flex;
  flex-direction: column;
  gap: 4px;
  width: 100%;
  --r-cf-h: 40px;
  --r-cf-pad-x: 12px;
  --r-cf-radius: 8px;
  --r-cf-color: var(--r-color-brand-primary);
  color: var(--r-color-fg);
  font-family: inherit;
}
.r-combobox-field--density-default {
  --r-cf-h: 48px;
  --r-cf-pad-x: 14px;
}
.r-combobox-field--density-comfortable {
  --r-cf-h: 40px;
  --r-cf-pad-x: 12px;
}
.r-combobox-field--density-compact {
  --r-cf-h: 32px;
  --r-cf-pad-x: 10px;
  --r-cf-radius: 6px;
}

.r-combobox-field__label {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: var(--r-font-weight-medium);
  line-height: 1.2;
  color: var(--r-color-fg-muted);
  transition: color var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-combobox-field__label--stacked {
  align-self: flex-start;
  padding-inline-start: 2px;
  margin-bottom: 4px;
}
.r-combobox-field:not(.r-combobox-field--disabled):focus-within
  .r-combobox-field__label--stacked {
  color: var(--r-cf-color);
}
.r-combobox-field--error .r-combobox-field__label--stacked {
  color: var(--r-color-danger);
}
.r-combobox-field__label--inline {
  flex-shrink: 0;
  align-self: stretch;
  padding: 0 10px;
  background: var(--r-color-bg-elevated);
  border-right: 1px solid var(--r-color-border);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-size: 11px;
  font-weight: var(--r-font-weight-bold);
  color: var(--r-color-fg-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  transition:
    background var(--r-motion-fast) var(--r-motion-ease-out),
    border-right-color var(--r-motion-fast) var(--r-motion-ease-out),
    color var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-combobox-field:not(.r-combobox-field--disabled):focus-within
  .r-combobox-field__label--inline {
  border-right-color: var(--r-cf-color);
}
.r-combobox-field--error .r-combobox-field__label--inline {
  border-right-color: var(--r-color-danger);
}

.r-combobox-field__field {
  display: flex;
  align-items: stretch;
  min-height: var(--r-cf-h);
  border-radius: var(--r-cf-radius);
  background: transparent;
  border: 1px solid transparent;
  transition:
    background var(--r-motion-med) var(--r-motion-ease-out),
    border-color var(--r-motion-med) var(--r-motion-ease-out),
    box-shadow var(--r-motion-med) cubic-bezier(0.34, 1.56, 0.64, 1);
  cursor: text;
}

.r-combobox-field--variant-outlined .r-combobox-field__field {
  border-color: var(--r-color-border);
  background: var(--r-color-bg-elevated);
}
.r-combobox-field--variant-filled .r-combobox-field__field {
  border-color: transparent;
  background: var(--r-color-surface);
}
.r-combobox-field--variant-underlined .r-combobox-field__field {
  border-radius: 0;
  background: transparent;
  border-bottom: 1px solid var(--r-color-border);
}
.r-combobox-field--variant-plain .r-combobox-field__field {
  background: transparent;
  border-color: transparent;
}

/* Hover — neutral fg halo on outlined, brand-tinted fill on filled.
   Mirrors RTextField so the two primitives read as siblings. */
.r-combobox-field--variant-outlined:not(.r-combobox-field--disabled)
  .r-combobox-field__field:hover {
  border-color: var(--r-color-border-strong);
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--r-color-fg) 6%, transparent);
}
.r-combobox-field--variant-filled:not(.r-combobox-field--disabled)
  .r-combobox-field__field:hover {
  background: color-mix(
    in srgb,
    var(--r-cf-color) 8%,
    var(--r-color-surface-hover)
  );
}
.r-combobox-field--variant-underlined:not(.r-combobox-field--disabled)
  .r-combobox-field__field:hover {
  border-bottom-color: var(--r-color-border-strong);
}

/* Focus-within = brand outline. Halo alpha + filled bg shift mirror
   RTextField's focused state. */
.r-combobox-field--variant-outlined:not(.r-combobox-field--disabled)
  .r-combobox-field__field:focus-within,
.r-combobox-field--variant-filled:not(.r-combobox-field--disabled)
  .r-combobox-field__field:focus-within {
  border-color: var(--r-cf-color);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--r-cf-color) 22%, transparent);
}
.r-combobox-field--variant-filled:not(.r-combobox-field--disabled)
  .r-combobox-field__field:focus-within {
  background: color-mix(
    in srgb,
    var(--r-cf-color) 10%,
    var(--r-color-surface-hover)
  );
}

/* Error tone. */
.r-combobox-field--error.r-combobox-field--variant-outlined
  .r-combobox-field__field,
.r-combobox-field--error.r-combobox-field--variant-filled
  .r-combobox-field__field {
  border-color: var(--r-color-danger) !important;
}
.r-combobox-field--error.r-combobox-field--variant-underlined
  .r-combobox-field__field {
  border-bottom-color: var(--r-color-danger);
}
.r-combobox-field--error .r-combobox-field__field:focus-within {
  box-shadow: 0 0 0 3px
    color-mix(in srgb, var(--r-color-danger) 22%, transparent) !important;
}

.r-combobox-field__chips {
  flex: 1;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px;
  padding: 6px var(--r-cf-pad-x);
  min-width: 0;
}

.r-combobox-field__chip {
  /* RTag handles tone surface; chips can wrap to multiple rows. */
}
.r-combobox-field__chip-close {
  appearance: none;
  background: transparent;
  border: 0;
  margin-left: 2px;
  margin-right: -4px;
  padding: 1px;
  display: inline-grid;
  place-items: center;
  border-radius: 3px;
  color: inherit;
  opacity: 0.7;
  cursor: pointer;
  transition: opacity var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-combobox-field__chip-close:hover {
  opacity: 1;
  background: color-mix(in srgb, currentColor 18%, transparent);
}

.r-combobox-field__input {
  flex: 1;
  min-width: 80px;
  border: 0;
  outline: 0;
  background: transparent;
  font: inherit;
  color: var(--r-color-fg);
  padding: 2px 0;
}
.r-combobox-field__input::placeholder {
  color: var(--r-color-fg-muted);
}

/* Field-level X — same vocabulary as RTextField's clearable. Sits at
   the right edge of the field, vertically centred on the chip row. */
.r-combobox-field__clear {
  appearance: none;
  background: transparent;
  border: 0;
  padding: 2px;
  margin-right: var(--r-cf-pad-x);
  align-self: center;
  cursor: pointer;
  color: var(--r-color-fg-muted);
  border-radius: 50%;
  display: inline-grid;
  place-items: center;
  flex-shrink: 0;
  transition:
    color var(--r-motion-fast) var(--r-motion-ease-out),
    background var(--r-motion-fast) var(--r-motion-ease-out),
    transform var(--r-motion-fast) cubic-bezier(0.34, 1.56, 0.64, 1);
}
.r-combobox-field__clear:hover {
  color: var(--r-cf-color);
  transform: scale(1.2);
}
.r-combobox-field__clear:active {
  transform: scale(0.92);
}

/* Disabled. */
.r-combobox-field--disabled {
  opacity: 0.55;
  cursor: not-allowed;
}
.r-combobox-field--disabled .r-combobox-field__field {
  cursor: not-allowed;
}
.r-combobox-field--disabled .r-combobox-field__input {
  cursor: not-allowed;
}

/* Details / hint / error row. Mirrors RTextField's gutter so the two
   primitives stack with identical bottom-edge padding. */
.r-combobox-field__details {
  padding-inline: 4px;
  font-size: 11px;
  line-height: 1.3;
  color: var(--r-color-fg-muted);
  min-height: 14px;
  transition: color var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-combobox-field__details--error {
  color: var(--r-color-danger);
}

/* ── Suggestion panel ─────────────────────────────────────────── */
.r-combobox-field__panel {
  position: fixed;
  z-index: var(--r-z-menu, 2500);
  background: var(--r-color-panel);
  border: 1px solid var(--r-color-panel-border);
  border-radius: 10px;
  box-shadow:
    0 20px 60px color-mix(in srgb, black 70%, transparent),
    0 4px 20px color-mix(in srgb, black 40%, transparent);
  backdrop-filter: blur(28px);
  -webkit-backdrop-filter: blur(28px);
  color: var(--r-color-fg);
  font-family: var(--r-font-family-sans);
  overflow: hidden;
}
.r-combobox-field__list {
  list-style: none;
  margin: 0;
  padding: 6px;
  overflow-x: hidden;
  overflow-y: auto;
  scrollbar-width: thin;
  scrollbar-color: var(--r-color-border-strong) transparent;
  max-height: inherit;
}
.r-combobox-field__item {
  padding: 8px 12px;
  border-radius: 8px;
  font-size: 13px;
  color: var(--r-color-fg-secondary);
  cursor: pointer;
  transition:
    background var(--r-motion-fast) var(--r-motion-ease-out),
    color var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-combobox-field__item:hover,
.r-combobox-field__item--active {
  background: var(--r-color-surface);
  color: var(--r-color-fg);
}

/* Pop motion — same vocabulary as RMenu / RSelect. */
.r-combobox-pop-enter-from {
  opacity: 0;
  transform: translateY(-4px) scale(0.98);
}
.r-combobox-pop-enter-active {
  transition:
    opacity 140ms var(--r-motion-ease-out),
    transform 220ms cubic-bezier(0.34, 1.56, 0.64, 1);
  transform-origin: top center;
}

@media (prefers-reduced-motion: reduce) {
  .r-combobox-pop-enter-from {
    transform: none;
  }
  .r-combobox-pop-enter-active {
    transition: opacity 100ms linear;
  }
}
</style>
