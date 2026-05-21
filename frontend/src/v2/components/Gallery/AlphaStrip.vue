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
import { computed } from "vue";

defineOptions({ inheritAttrs: false });

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
</script>

<template>
  <aside class="alpha-strip" aria-label="Jump to letter">
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
      :aria-label="`Jump to ${l}`"
      @click="availableSet.has(l) && $emit('pick', l)"
    >
      {{ l }}
    </button>
  </aside>
</template>

<style scoped>
.alpha-strip {
  width: 24px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 8px 0;
  /* Breathe away from the viewport edge — the strip shouldn't touch the
     right border of the gallery section. */
  margin-right: 12px;
  user-select: none;
}

.alpha-strip__btn {
  appearance: none;
  background: transparent;
  border: 0;
  font-family: inherit;
  font-size: 12px;
  font-weight: var(--r-font-weight-bold);
  color: var(--r-color-fg-faint);
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

html[data-bp~="xs"] .alpha-strip {
  width: 16px;
}
html[data-bp~="xs"] .alpha-strip__btn {
  font-size: 7px;
  padding: 1px 0;
}
</style>
