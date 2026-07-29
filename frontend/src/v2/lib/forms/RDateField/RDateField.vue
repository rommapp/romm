<script setup lang="ts">
// RDateField — date picker primitive. The input itself stays minimal
// (an RTextField shell so it inherits variants, densities, labels, error
// states), but the calendar popover is fully owned by v2 — same glass
// panel + spring-in motion as RMenu / RDialog, modality-gated focus
// rings on day cells, keyboard navigation, locale-aware weekday and
// month names via `Intl.DateTimeFormat`.
//
// The native `<input type="date">` browser popup is intentionally not
// used: it ignores theme tokens, fights the v2 visual language, and
// reads differently on every OS.
//
// Model value accepts whatever the call site already has (Date object,
// UNIX timestamp in milliseconds, ISO/yyyy-MM-dd string, or null) and
// emits a `Date | null` anchored at UTC midnight so timezone shifts
// don't bump the value across day boundaries.
import {
  autoUpdate,
  flip,
  offset as offsetMiddleware,
  shift,
  useFloating,
} from "@floating-ui/vue";
import {
  computed,
  nextTick,
  onBeforeUnmount,
  onMounted,
  ref,
  watch,
} from "vue";
import RBtn from "../../primitives/RBtn/RBtn.vue";
import RIcon from "../../primitives/RIcon/RIcon.vue";
import RTextField from "../RTextField/RTextField.vue";

defineOptions({ inheritAttrs: false });

interface Props {
  /** Current value. Accepts any common date shape so call sites don't
   *  have to pre-convert. Emitted value is always `Date | null`. */
  modelValue?: Date | number | string | null;
  /** First day of the week shown in the calendar grid. 0=Sunday,
   *  1=Monday, … Default Monday — matches European locales. */
  firstDayOfWeek?: 0 | 1 | 2 | 3 | 4 | 5 | 6;
  /** Earliest selectable date. Days before are rendered but disabled. */
  min?: Date | number | string | null;
  /** Latest selectable date. Days after are rendered but disabled. */
  max?: Date | number | string | null;
  /** Footer "today" shortcut label. Defaults to "Today". */
  todayLabel?: string;
  /** Footer "clear" shortcut label. Defaults to "Clear". */
  clearLabel?: string;
  /** Hide the today/clear footer row. */
  hideFooter?: boolean;
  /** Disable opening the picker. RTextField also accepts `disabled` —
   *  we forward it to the field so it gets the muted look too. */
  disabled?: boolean;
  /** Override the display format. Defaults to `dateStyle: medium`. */
  displayFormat?: Intl.DateTimeFormatOptions;
  /** Render an inline X next to the calendar icon when a date is set.
   *  Mirrors RTextField's clearable affordance so the two primitives
   *  read as siblings on dialogs that mix text + date fields. */
  clearable?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
  modelValue: null,
  firstDayOfWeek: 1,
  min: null,
  max: null,
  todayLabel: "Today",
  clearLabel: "Clear",
  hideFooter: false,
  disabled: false,
  displayFormat: () => ({ dateStyle: "medium" }),
  clearable: false,
});

const emit = defineEmits<{
  (e: "update:modelValue", value: Date | null): void;
}>();

// ── Value normalization ────────────────────────────────────────
function toDate(v: Date | number | string | null | undefined): Date | null {
  if (v == null || v === "") return null;
  const d =
    v instanceof Date
      ? v
      : typeof v === "number"
        ? new Date(v)
        : new Date(String(v));
  return Number.isNaN(d.getTime()) ? null : d;
}

const selectedDate = computed(() => toDate(props.modelValue));
const minDate = computed(() => toDate(props.min));
const maxDate = computed(() => toDate(props.max));

// Format the display value with locale-aware text. `undefined` locale
// = navigator default, same call shape Intl prefers for "user locale".
const displayValue = computed(() => {
  if (!selectedDate.value) return "";
  return new Intl.DateTimeFormat(undefined, props.displayFormat).format(
    selectedDate.value,
  );
});

// ── Open state + floating-ui ───────────────────────────────────
const isOpen = ref(false);
const referenceEl = ref<HTMLElement | null>(null);
const panelRef = ref<HTMLElement | null>(null);

const { floatingStyles } = useFloating(referenceEl, panelRef, {
  placement: "bottom-start",
  strategy: "fixed",
  open: isOpen,
  transform: false,
  whileElementsMounted: autoUpdate,
  middleware: [
    offsetMiddleware(6),
    flip({ padding: 8 }),
    shift({ padding: 8 }),
  ],
});

function open() {
  if (props.disabled) return;
  if (isOpen.value) return;
  isOpen.value = true;
}
function close() {
  if (!isOpen.value) return;
  isOpen.value = false;
}
function toggle() {
  if (isOpen.value) close();
  else open();
}

// ── Calendar view state ────────────────────────────────────────
// `viewMonth` is the first day of the displayed month (always day 1).
// `focusedDay` tracks the keyboard cursor — separate from selection so
// users can navigate without committing.
function startOfMonth(d: Date): Date {
  return new Date(d.getFullYear(), d.getMonth(), 1);
}
function sameDay(a: Date | null, b: Date | null): boolean {
  if (!a || !b) return false;
  return (
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate()
  );
}

const viewMonth = ref<Date>(startOfMonth(selectedDate.value ?? new Date()));
const focusedDay = ref<Date>(selectedDate.value ?? new Date());

// Whenever the popup opens, snap the view + cursor back to the current
// selection (or today) so the user never lands on a stale month.
watch(isOpen, (next) => {
  if (!next) return;
  const anchor = selectedDate.value ?? new Date();
  viewMonth.value = startOfMonth(anchor);
  focusedDay.value = new Date(anchor);
  nextTick(focusDayCell);
});

// ── Grid building ──────────────────────────────────────────────
interface GridCell {
  date: Date;
  inMonth: boolean;
  isToday: boolean;
  isSelected: boolean;
  isDisabled: boolean;
  isFocused: boolean;
  key: string;
}

const today = computed(() => new Date());

function isDisabledDate(d: Date): boolean {
  if (minDate.value && d < startOfDay(minDate.value)) return true;
  if (maxDate.value && d > endOfDay(maxDate.value)) return true;
  return false;
}
function startOfDay(d: Date): Date {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate(), 0, 0, 0, 0);
}
function endOfDay(d: Date): Date {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate(), 23, 59, 59, 999);
}

const grid = computed<GridCell[]>(() => {
  const first = startOfMonth(viewMonth.value);
  const startOffset = (first.getDay() - props.firstDayOfWeek + 7) % 7;
  const gridStart = new Date(first);
  gridStart.setDate(first.getDate() - startOffset);

  const cells: GridCell[] = [];
  for (let i = 0; i < 42; i += 1) {
    const d = new Date(gridStart);
    d.setDate(gridStart.getDate() + i);
    cells.push({
      date: d,
      inMonth: d.getMonth() === viewMonth.value.getMonth(),
      isToday: sameDay(d, today.value),
      isSelected: sameDay(d, selectedDate.value),
      isDisabled: isDisabledDate(d),
      isFocused: sameDay(d, focusedDay.value),
      key: `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`,
    });
  }
  return cells;
});

// ── Locale-aware labels ────────────────────────────────────────
const monthYearFormat = new Intl.DateTimeFormat(undefined, {
  month: "long",
  year: "numeric",
});
const monthLabel = computed(() => monthYearFormat.format(viewMonth.value));

const weekdayFormat = new Intl.DateTimeFormat(undefined, { weekday: "short" });
const weekdays = computed(() => {
  // Anchor on a known Sunday (2024-01-07) and step `firstDayOfWeek` ahead.
  const anchor = new Date(2024, 0, 7);
  const out: string[] = [];
  for (let i = 0; i < 7; i += 1) {
    const d = new Date(anchor);
    d.setDate(anchor.getDate() + ((i + props.firstDayOfWeek) % 7));
    out.push(weekdayFormat.format(d));
  }
  return out;
});

// ── Month / year navigation ────────────────────────────────────
function shiftMonth(delta: number) {
  viewMonth.value = new Date(
    viewMonth.value.getFullYear(),
    viewMonth.value.getMonth() + delta,
    1,
  );
}
function shiftYear(delta: number) {
  viewMonth.value = new Date(
    viewMonth.value.getFullYear() + delta,
    viewMonth.value.getMonth(),
    1,
  );
}

// ── Selection ──────────────────────────────────────────────────
function selectDay(d: Date) {
  if (isDisabledDate(d)) return;
  // Emit UTC midnight so the round-trip survives timezones — matches the
  // shape callers already store (e.g. `released_at` timestamps in DB).
  const utc = Date.UTC(d.getFullYear(), d.getMonth(), d.getDate());
  emit("update:modelValue", new Date(utc));
  close();
}
function selectToday() {
  const t = today.value;
  selectDay(t);
}
function clearValue() {
  emit("update:modelValue", null);
  close();
}

// ── Keyboard navigation inside the panel ───────────────────────
// Day cells are real `<button>`s so Tab order works out of the box;
// these handlers cover the rich grid-style navigation users expect.
function onPanelKeydown(evt: KeyboardEvent) {
  if (!isOpen.value) return;
  switch (evt.key) {
    case "ArrowLeft":
      evt.preventDefault();
      moveFocus(-1);
      break;
    case "ArrowRight":
      evt.preventDefault();
      moveFocus(1);
      break;
    case "ArrowUp":
      evt.preventDefault();
      moveFocus(-7);
      break;
    case "ArrowDown":
      evt.preventDefault();
      moveFocus(7);
      break;
    case "Home":
      evt.preventDefault();
      moveFocusToWeekEdge(-1);
      break;
    case "End":
      evt.preventDefault();
      moveFocusToWeekEdge(1);
      break;
    case "PageUp":
      evt.preventDefault();
      if (evt.shiftKey) shiftYear(-1);
      else shiftMonth(-1);
      break;
    case "PageDown":
      evt.preventDefault();
      if (evt.shiftKey) shiftYear(1);
      else shiftMonth(1);
      break;
    case "Enter":
    case " ":
      // The day button handles its own click; only intercept if focus
      // is not on a day cell (e.g. on month nav arrows).
      if (
        !(evt.target as HTMLElement | null)?.classList.contains(
          "r-date-cal__day",
        )
      ) {
        return;
      }
      evt.preventDefault();
      selectDay(new Date(focusedDay.value));
      break;
    case "Escape":
      evt.preventDefault();
      evt.stopPropagation();
      close();
      // Send focus back to the field so tab order doesn't get stranded
      // on a teleported panel that just unmounted.
      nextTick(() => {
        (
          referenceEl.value?.querySelector("input") as HTMLElement | null
        )?.focus();
      });
      break;
    default:
      break;
  }
}

function moveFocus(deltaDays: number) {
  const next = new Date(focusedDay.value);
  next.setDate(next.getDate() + deltaDays);
  focusedDay.value = next;
  // If the cursor walked off-month, scroll the view to follow it so the
  // cell stays visible.
  if (
    next.getFullYear() !== viewMonth.value.getFullYear() ||
    next.getMonth() !== viewMonth.value.getMonth()
  ) {
    viewMonth.value = startOfMonth(next);
  }
  nextTick(focusDayCell);
}
function moveFocusToWeekEdge(direction: -1 | 1) {
  // -1: Home → start of week. +1: End → end of week.
  const dow = focusedDay.value.getDay();
  const fdow = props.firstDayOfWeek;
  const offsetFromStart = (dow - fdow + 7) % 7;
  const next = new Date(focusedDay.value);
  if (direction === -1) {
    next.setDate(next.getDate() - offsetFromStart);
  } else {
    next.setDate(next.getDate() + (6 - offsetFromStart));
  }
  focusedDay.value = next;
  nextTick(focusDayCell);
}

function focusDayCell() {
  if (!panelRef.value) return;
  const key = `${focusedDay.value.getFullYear()}-${focusedDay.value.getMonth()}-${focusedDay.value.getDate()}`;
  const cell = panelRef.value.querySelector(
    `[data-day-key="${key}"]`,
  ) as HTMLElement | null;
  cell?.focus();
}

// ── Field-level keyboard wiring ────────────────────────────────
// On the closed field: Space / Enter / ArrowDown opens the popup. Tab
// behaves natively (moves to next focusable). When open, Escape closes
// (handled inside the panel — the field doesn't see keydown when focus
// has moved into the calendar).
function onFieldKeydown(evt: KeyboardEvent) {
  if (props.disabled) return;
  if (isOpen.value) return;
  if (evt.key === " " || evt.key === "Enter" || evt.key === "ArrowDown") {
    evt.preventDefault();
    open();
  }
}

// ── Click-outside ──────────────────────────────────────────────
function onDocPointerDown(evt: PointerEvent) {
  if (!isOpen.value) return;
  const target = evt.target as Node | null;
  if (!target) return;
  if (referenceEl.value?.contains(target as HTMLElement)) return;
  if (panelRef.value?.contains(target)) return;
  close();
}

onMounted(() => {
  document.addEventListener("pointerdown", onDocPointerDown, true);
});
onBeforeUnmount(() => {
  document.removeEventListener("pointerdown", onDocPointerDown, true);
});
</script>

<template>
  <!-- combobox role goes here, not on RTextField: with a visible label
       RTextField renders a <label>, where the role is disallowed and voids
       the input's label association. -->
  <!-- eslint-disable-next-line vuejs-accessibility/no-static-element-interactions -->
  <div
    ref="referenceEl"
    class="r-date-field"
    role="combobox"
    aria-haspopup="dialog"
    :aria-expanded="isOpen"
    @keydown="onFieldKeydown"
  >
    <!-- Single `@click` on the wrapper is enough: native clicks on
         every part of the field (input, icon, label well) bubble up
         here. We deliberately don't subscribe to `click:append-inner` —
         that would fire alongside the bubbled click and toggle twice. -->
    <RTextField
      v-bind="$attrs"
      :model-value="displayValue"
      :disabled="disabled"
      :focused="isOpen"
      readonly
      :append-inner-icon="
        clearable && selectedDate ? undefined : 'mdi-calendar'
      "
      @click="toggle"
    >
      <template v-if="clearable && selectedDate" #append-inner>
        <!-- Inline clear — wipes the value without opening the picker.
             `mousedown.prevent` keeps focus on the field so subsequent
             keypresses don't surprise the user by reaching the body. -->
        <button
          type="button"
          class="r-date-field__clear"
          :aria-label="clearLabel"
          @mousedown.prevent
          @click.stop="clearValue"
        >
          <RIcon icon="mdi-close-circle" size="x-small" />
        </button>
      </template>
    </RTextField>

    <Teleport to="body">
      <Transition name="r-date-pop">
        <!-- eslint-disable-next-line vuejs-accessibility/no-static-element-interactions -->
        <div
          v-if="isOpen"
          ref="panelRef"
          class="r-date-cal"
          :style="floatingStyles"
          role="dialog"
          aria-label="Date picker"
          @keydown="onPanelKeydown"
        >
          <!-- Header — month/year title flanked by nav arrows. The
               outer two step a year, the inner two step a month, so the
               common moves are both one click away. -->
          <div class="r-date-cal__head">
            <button
              type="button"
              class="r-date-cal__nav"
              aria-label="Previous year"
              @click="shiftYear(-1)"
            >
              <RIcon icon="mdi-chevron-double-left" size="x-small" />
            </button>
            <button
              type="button"
              class="r-date-cal__nav"
              aria-label="Previous month"
              @click="shiftMonth(-1)"
            >
              <RIcon icon="mdi-chevron-left" size="x-small" />
            </button>

            <div class="r-date-cal__title" aria-live="polite">
              {{ monthLabel }}
            </div>

            <button
              type="button"
              class="r-date-cal__nav"
              aria-label="Next month"
              @click="shiftMonth(1)"
            >
              <RIcon icon="mdi-chevron-right" size="x-small" />
            </button>
            <button
              type="button"
              class="r-date-cal__nav"
              aria-label="Next year"
              @click="shiftYear(1)"
            >
              <RIcon icon="mdi-chevron-double-right" size="x-small" />
            </button>
          </div>

          <!-- Weekday header. `aria-hidden` because the day cells carry
               full-date aria-labels — reading the column header twice
               would be noise. -->
          <div class="r-date-cal__weekdays" aria-hidden="true">
            <span
              v-for="(w, i) in weekdays"
              :key="i"
              class="r-date-cal__weekday"
            >
              {{ w }}
            </span>
          </div>

          <!-- Day grid. 6 × 7 = 42 cells; days from neighbouring months
               render muted (`--out`). The Tab order is the focused day
               only (`tabindex` rovers); arrow keys do the rest. -->
          <div class="r-date-cal__grid" role="grid">
            <button
              v-for="cell in grid"
              :key="cell.key"
              type="button"
              class="r-date-cal__day"
              :class="{
                'r-date-cal__day--out': !cell.inMonth,
                'r-date-cal__day--today': cell.isToday,
                'r-date-cal__day--selected': cell.isSelected,
                'r-date-cal__day--disabled': cell.isDisabled,
              }"
              :data-day-key="cell.key"
              :tabindex="cell.isFocused ? 0 : -1"
              :aria-selected="cell.isSelected"
              :aria-disabled="cell.isDisabled || undefined"
              :disabled="cell.isDisabled"
              @click="selectDay(cell.date)"
            >
              {{ cell.date.getDate() }}
            </button>
          </div>

          <!-- Footer shortcuts. Hidden when the consumer doesn't want
               quick-access buttons (e.g. embedded in a complex form). -->
          <div v-if="!hideFooter" class="r-date-cal__foot">
            <RBtn variant="text" size="small" @click="selectToday">
              {{ todayLabel }}
            </RBtn>
            <RBtn
              variant="text"
              size="small"
              color="danger"
              :disabled="!selectedDate"
              @click="clearValue"
            >
              {{ clearLabel }}
            </RBtn>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<style scoped>
.r-date-field {
  display: block;
  width: 100%;
}

/* Readonly input — the whole field acts as the popup activator, so it
   stays clickable end-to-end. The caret is distracting on a value the
   user can't edit, so we hide it. */
.r-date-field :deep(.r-text-field__field) {
  cursor: pointer;
}
.r-date-field :deep(.r-text-field__input) {
  cursor: pointer;
  caret-color: transparent;
  user-select: none;
}
.r-date-field :deep(.r-text-field--disabled .r-text-field__field),
.r-date-field :deep(.r-text-field--disabled .r-text-field__input) {
  cursor: not-allowed;
}

/* Clear button — mirrors the X RTextField renders for `clearable`. We
   can't reuse the native clearable affordance because RTextField's
   model-value here is a derived display string; clearing has to emit
   `null` upward via the picker's own emit path. */
.r-date-field__clear {
  appearance: none;
  background: transparent;
  border: 0;
  padding: 2px;
  cursor: pointer;
  color: var(--r-color-fg-muted);
  border-radius: 50%;
  display: inline-grid;
  place-items: center;
  transition:
    color var(--r-motion-fast) var(--r-motion-ease-out),
    background var(--r-motion-fast) var(--r-motion-ease-out),
    transform var(--r-motion-fast) cubic-bezier(0.34, 1.56, 0.64, 1);
}
.r-date-field__clear:hover {
  color: var(--r-color-brand-primary);
  transform: scale(1.2);
}
.r-date-field__clear:active {
  transform: scale(0.92);
}

/* ── Calendar panel ────────────────────────────────────────────── */
.r-date-cal {
  position: fixed;
  z-index: var(--r-z-menu, 2500);
  width: 280px;
  padding: 8px;
  background: var(--r-color-panel);
  border: 1px solid var(--r-color-panel-border);
  border-radius: 12px;
  box-shadow:
    0 20px 60px color-mix(in srgb, black 70%, transparent),
    0 4px 20px color-mix(in srgb, black 40%, transparent);
  backdrop-filter: blur(28px);
  color: var(--r-color-fg);
  font-family: var(--r-font-family-sans);
  display: flex;
  flex-direction: column;
  gap: 6px;
}

/* ── Header ────────────────────────────────────────────────────── */
.r-date-cal__head {
  display: grid;
  grid-template-columns: auto auto 1fr auto auto;
  align-items: center;
  gap: 2px;
  padding: 2px 4px 4px;
}
.r-date-cal__title {
  text-align: center;
  font-size: 13px;
  font-weight: var(--r-font-weight-bold);
  letter-spacing: 0.02em;
  text-transform: capitalize;
  color: var(--r-color-fg);
  padding: 0 6px;
  /* Force ellipsis if a locale renders a very long month name. */
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.r-date-cal__nav {
  appearance: none;
  background: transparent;
  border: 0;
  border-radius: 6px;
  width: 28px;
  height: 28px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: var(--r-color-fg-secondary);
  cursor: pointer;
  transition:
    background var(--r-motion-fast) var(--r-motion-ease-out),
    color var(--r-motion-fast) var(--r-motion-ease-out),
    transform var(--r-motion-fast) cubic-bezier(0.34, 1.56, 0.64, 1);
}
.r-date-cal__nav:hover {
  background: color-mix(in srgb, var(--r-color-fg) 10%, transparent);
  color: var(--r-color-fg);
}
.r-date-cal__nav:active {
  transform: scale(0.92);
}

/* ── Weekday header ────────────────────────────────────────────── */
.r-date-cal__weekdays {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 2px;
  padding: 0 2px;
}
.r-date-cal__weekday {
  text-align: center;
  font-size: 10px;
  font-weight: var(--r-font-weight-bold);
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--r-color-fg-muted);
  padding: 4px 0;
}

/* ── Day grid ──────────────────────────────────────────────────── */
.r-date-cal__grid {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 2px;
  padding: 0 2px;
}

.r-date-cal__day {
  appearance: none;
  background: transparent;
  border: 0;
  border-radius: 8px;
  aspect-ratio: 1 / 1;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font: inherit;
  font-size: 13px;
  font-weight: var(--r-font-weight-medium);
  color: var(--r-color-fg);
  cursor: pointer;
  /* Sits inside an aspect-ratio cell so it scales with width. */
  padding: 0;
  position: relative;
  transition:
    background var(--r-motion-fast) var(--r-motion-ease-out),
    color var(--r-motion-fast) var(--r-motion-ease-out),
    transform var(--r-motion-fast) cubic-bezier(0.34, 1.56, 0.64, 1);
}
.r-date-cal__day:hover:not(:disabled) {
  background: color-mix(in srgb, var(--r-color-fg) 12%, transparent);
}
.r-date-cal__day:active:not(:disabled) {
  transform: scale(0.92);
}

/* Days that bleed in from the neighbouring months — keep them visible
   but obviously secondary so the eye reads the in-month block first. */
.r-date-cal__day--out {
  color: var(--r-color-fg-faint);
}

/* Today — a small dot under the digit instead of recolouring the cell
   so a "today + selected" state still reads as selected. */
.r-date-cal__day--today::after {
  content: "";
  position: absolute;
  bottom: 4px;
  left: 50%;
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: var(--r-color-brand-primary);
  transform: translateX(-50%);
}
.r-date-cal__day--today.r-date-cal__day--selected::after {
  background: white;
}

/* Selected — full brand fill, white digits. Matches the rest of the
   lib (RCheckbox icon, RBtn primary text) which use plain `white`
   against the brand fill. */
.r-date-cal__day--selected {
  background: var(--r-color-brand-primary);
  color: white;
}
.r-date-cal__day--selected:hover:not(:disabled) {
  background: color-mix(in srgb, var(--r-color-brand-primary) 90%, white);
}

/* Disabled — past min / after max. */
.r-date-cal__day--disabled,
.r-date-cal__day:disabled {
  cursor: not-allowed;
  color: var(--r-color-fg-faint);
  opacity: 0.4;
}

/* ── Footer ────────────────────────────────────────────────────── */
.r-date-cal__foot {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 4px 2px 0;
  border-top: 1px solid var(--r-color-border);
  margin-top: 2px;
  padding-top: 6px;
}

/* ── Modality-gated focus ──────────────────────────────────────── */
/* Mirrors the rest of the lib — outline only paints when the user is
   on keyboard / gamepad. `:focus` alone would flash on every click. */
html[data-input="key"] .r-date-cal__day:focus,
html[data-input="pad"] .r-date-cal__day:focus,
html[data-input="key"] .r-date-cal__nav:focus,
html[data-input="pad"] .r-date-cal__nav:focus {
  outline: 2px solid var(--r-color-brand-primary);
  outline-offset: 2px;
}
.r-date-cal__day:focus,
.r-date-cal__nav:focus {
  outline: none;
}

/* ── Open / close motion ──────────────────────────────────────── */
/* Same vocabulary RMenu uses — spring scale-in from top, instant close. */
.r-date-pop-enter-from {
  opacity: 0;
  transform: translateY(-4px) scale(0.98);
}
.r-date-pop-enter-active {
  transition:
    opacity 140ms var(--r-motion-ease-out),
    transform 220ms cubic-bezier(0.34, 1.56, 0.64, 1);
  transform-origin: top center;
}

@media (prefers-reduced-motion: reduce) {
  .r-date-pop-enter-from {
    transform: none;
  }
  .r-date-pop-enter-active {
    transition: opacity 100ms linear;
  }
  .r-date-cal__day,
  .r-date-cal__nav {
    transition: none;
  }
}
</style>
