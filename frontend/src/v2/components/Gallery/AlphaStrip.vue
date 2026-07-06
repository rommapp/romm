<script setup lang="ts">
// AlphaStrip — A-Z-# jump sidebar for letter-grouped grids (Platform and
// Collection gallery). Feature composite — not a design-system primitive.
//
// Two highlight signals are supported:
//   * `current` — single letter used to mark a deliberate jump (e.g. the
//     user clicked "F"). One active at a time.
//   * `visible` — a Set of every letter whose section currently intersects
//     the viewport. Multiple letters light up together when the first row
//     of the grid spans several groups (A, B, C, …).
//
// When both are set, `visible` wins visually because it reflects the real
// scroll position.
import { computed, ref } from "vue";
import { useI18n } from "vue-i18n";

defineOptions({ inheritAttrs: false });

const { t } = useI18n();

// Two non-alphabetic buckets bookend the alphabet:
//   * `#` — digits (0-9) — sits BEFORE A
//   * `@` — any other non-alphanumeric first character — sits AFTER Z
// Order in asc: `# A B … Z @` — `#` at the top, `@` at the bottom.
// When the gallery sorts desc the whole array reverses (`@` to the top,
// `#` to the bottom) so the strip's visual order tracks the data's
// order and the scroll-spy highlight follows the scroll direction.
const ALPHABET = "#ABCDEFGHIJKLMNOPQRSTUVWXYZ@".split("");

interface Props {
  available?: Set<string> | string[];
  current?: string;
  visible?: Set<string> | string[];
  /** Render order — reversed when the gallery sorts descending. */
  direction?: "asc" | "desc";
}

const props = withDefaults(defineProps<Props>(), {
  available: () => new Set<string>(),
  current: "",
  visible: () => new Set<string>(),
  direction: "asc",
});

const letters = computed(() =>
  props.direction === "desc" ? [...ALPHABET].reverse() : ALPHABET,
);

defineEmits<{
  (e: "pick", letter: string): void;
}>();

const availableSet = computed(() => {
  const a = props.available;
  return a instanceof Set ? a : new Set(a);
});

const visibleSet = computed(() => {
  const v = props.visible;
  return v instanceof Set ? v : new Set(v);
});

function isActive(letter: string): boolean {
  if (visibleSet.value.size > 0) return visibleSet.value.has(letter);
  return props.current === letter;
}

// ── Keyboard roving ──────────────────────────────────────────────
// The strip is a SINGLE tab stop (mirrors the gallery grid): Tab lands
// on one letter, Arrow Up/Down move between the AVAILABLE letters
// (disabled ones are skipped), Home/End jump to the ends. Only enabled
// letters are reachable — the rest are `:disabled` and never focusable.
const stripEl = ref<HTMLElement | null>(null);
// The letter the user last moved to; pins the tab stop once they steer.
const steeredLetter = ref<string | null>(null);

const availableLetters = computed(() =>
  letters.value.filter((l) => availableSet.value.has(l)),
);

// The single tab stop: the letter the user steered to, else the
// scroll-spied current letter, else the first available one — so Tab
// into the strip lands where the gallery currently is.
const rovingLetter = computed<string | null>(() => {
  const avail = availableLetters.value;
  if (steeredLetter.value && avail.includes(steeredLetter.value))
    return steeredLetter.value;
  if (props.current && avail.includes(props.current)) return props.current;
  return avail[0] ?? null;
});

function focusLetter(letter: string) {
  steeredLetter.value = letter;
  stripEl.value
    ?.querySelector<HTMLElement>(`[data-letter="${letter}"]`)
    ?.focus();
}

function onKeydown(e: KeyboardEvent) {
  const avail = availableLetters.value;
  if (avail.length === 0) return;
  const active = document.activeElement as HTMLElement | null;
  let idx = active
    ? avail.indexOf(active.getAttribute("data-letter") ?? "")
    : -1;

  switch (e.key) {
    case "ArrowDown":
      idx = idx < 0 ? 0 : Math.min(idx + 1, avail.length - 1);
      break;
    case "ArrowUp":
      idx = idx < 0 ? 0 : Math.max(idx - 1, 0);
      break;
    case "Home":
      idx = 0;
      break;
    case "End":
      idx = avail.length - 1;
      break;
    default:
      return;
  }
  e.preventDefault();
  focusLetter(avail[idx]);
}
</script>

<template>
  <aside
    ref="stripEl"
    class="alpha-strip"
    :aria-label="t('gallery.jump-to-letter')"
    @keydown="onKeydown"
  >
    <button
      v-for="l in letters"
      :key="l"
      type="button"
      class="alpha-strip__btn"
      :class="{
        'alpha-strip__btn--has': availableSet.has(l),
        'alpha-strip__btn--current': isActive(l),
      }"
      :disabled="!availableSet.has(l)"
      :data-letter="l"
      :tabindex="
        availableSet.has(l) ? (l === rovingLetter ? 0 : -1) : undefined
      "
      :aria-label="`Jump to ${l}`"
      @click="availableSet.has(l) && $emit('pick', l)"
    >
      {{ l }}
    </button>
  </aside>
</template>

<style scoped>
.alpha-strip {
  /* Width + edge gap come from the section (`--r-alpha-strip-*`) so the
     stuck-toolbar overlay, which insets by the same footprint, stays in
     lockstep with the strip at every breakpoint. */
  width: var(--r-alpha-strip-w, 24px);
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 8px 0;
  /* Breathe away from the viewport edge — the strip shouldn't touch the
     right border of the gallery section. */
  margin-right: var(--r-alpha-strip-gap, 12px);
  user-select: none;
}

.alpha-strip__btn {
  appearance: none;
  background: transparent;
  border: 0;
  font-family: inherit;
  font-size: 12px;
  font-weight: var(--r-font-weight-bold);
  color: var(--r-color-fg-faint-hard);
  cursor: default;
  line-height: 1;
  padding: 3px;
  margin-top: 4px;
  width: 100%;
  text-align: center;
  border-radius: 3px;
  transition:
    color var(--r-motion-med) var(--r-motion-ease-out),
    background var(--r-motion-fast) var(--r-motion-ease-out);
}

.alpha-strip__btn--has {
  color: var(--r-color-fg-muted);
  cursor: pointer;
}
.alpha-strip__btn--has:hover {
  color: var(--r-color-fg);
  background: var(--r-color-surface);
}

/* Scroll-spied letter — primary brand colour to stand out against the
   plain-white `--has` letters. */
.alpha-strip__btn--current,
.alpha-strip__btn--has.alpha-strip__btn--current {
  color: var(--r-color-brand-primary) !important;
  background: var(--r-color-surface-hover);
}
.alpha-strip__btn--has.alpha-strip__btn--current:hover {
  color: var(--r-color-brand-primary-hover) !important;
  background: color-mix(in srgb, var(--r-color-brand-primary) 12%, transparent);
}

/* On phones the gallery section extends UNDER the translucent bottom tab bar
   (the glass effect), so centring the strip in the section drops the letters
   low — nearer the bottom bar than the top nav. Reserve the bar's height as
   bottom padding so the letters centre in the VISIBLE content band instead. */
html[data-bp~="sm-and-down"] .alpha-strip {
  padding-bottom: calc(
    var(--r-space-2) + var(--r-bottom-nav-h) + env(safe-area-inset-bottom)
  );
}

/* Phones: the column width / edge gap come from the section vars (see
   `.alpha-strip`), which are widened on `xs`. Here we just bump the letters
   up to something more legible / tappable. Font + spacing stay capped so all
   26 letters still fit the available height without clipping on a short screen
   (a proper drag-scrubber is a separate redesign). */
html[data-bp~="xs"] .alpha-strip__btn {
  font-size: 11px;
  padding: 2px 0;
  margin-top: 2px;
}
</style>
