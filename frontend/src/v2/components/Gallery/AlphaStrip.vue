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
// scroll position. Letters that don't fit scroll within the strip.
//
// `grid` lays the letters out as a wrapping grid instead of a column, for the
// phone and tablet jump menu (AlphaJumpMenu).
import { computed, ref, watch } from "vue";
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
  /** Lay the letters out as a wrapping grid instead of a column. */
  grid?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
  available: () => new Set<string>(),
  current: "",
  visible: () => new Set<string>(),
  direction: "asc",
  grid: false,
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

const rootEl = ref<HTMLElement | null>(null);
const activeLetters = computed(() => letters.value.filter(isActive).join(""));

// Keep the highlighted letters in view, the first one winning if they don't
// all fit. Measured on screen: the strip's end can sit below the viewport.
watch(
  activeLetters,
  (active) => {
    const root = rootEl.value;
    if (!active || !root || root.scrollHeight <= root.clientHeight) return;
    const btnRect = (letter: string) =>
      root.querySelector(`[data-letter="${letter}"]`)?.getBoundingClientRect();
    const first = btnRect(active[0]);
    const last = btnRect(active[active.length - 1]);
    if (!first || !last) return;
    const style = getComputedStyle(root);
    const box = root.getBoundingClientRect();
    const top = box.top + parseFloat(style.paddingTop);
    const bottom =
      Math.min(box.bottom, window.innerHeight) -
      parseFloat(style.paddingBottom);
    let delta = Math.max(0, Math.min(last.bottom - bottom, first.top - top));
    if (first.top < top) delta = first.top - top;
    if (delta) root.scrollBy({ top: delta, behavior: "smooth" });
  },
  { flush: "post" },
);
</script>

<template>
  <aside
    v-bind="$attrs"
    ref="rootEl"
    class="alpha-strip r-v2-scroll-hidden"
    :class="{ 'alpha-strip--grid': grid }"
    :aria-label="t('gallery.jump-to-letter')"
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
      :data-letter="l"
      :disabled="!availableSet.has(l)"
      :aria-label="t('gallery.jump-to', { letter: l })"
      @click="availableSet.has(l) && $emit('pick', l)"
    >
      {{ l }}
    </button>
  </aside>
</template>

<style scoped>
.alpha-strip {
  /* Width + edge gap come from the section (`--r-alpha-strip-*`). */
  width: var(--r-alpha-strip-w, 24px);
  display: flex;
  flex-direction: column;
  align-items: center;
  /* `safe`: once the letters overflow, centring would push the first ones out
     of reach above the scroll origin. */
  justify-content: safe center;
  overflow-y: auto;
  overscroll-behavior: contain;
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

.alpha-strip--grid {
  width: auto;
  display: grid;
  grid-template-columns: repeat(7, var(--r-touch-target));
  justify-content: center;
  gap: var(--r-space-1);
  overflow: visible;
  padding: var(--r-space-2);
  margin-right: 0;
}
.alpha-strip--grid .alpha-strip__btn {
  height: var(--r-touch-target);
  margin-top: 0;
  font-size: var(--r-font-size-lg);
  border-radius: var(--r-radius-sm);
}
</style>
