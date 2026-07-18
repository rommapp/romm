<script setup lang="ts">
// RSteps — horizontal step indicator. A row of numbered dots connected
// by progress lines. Pure presentation: no stores, no router, no domain
// knowledge. Drive it with the current step number and the total.
//
// Three states map cleanly to the dot's `data-state`:
//   * past    — solid brand fill, white number
//   * current — solid brand fill, white number, scaled up with a
//               pulsing halo so it stands out from the past dots
//   * future  — muted outline, faint number
//
// `direction` lets the caller hint whether the user moved forward or
// back. It's used for transitions only; the line fill always animates
// scaleX from a left origin, so growing reads as forward and shrinking
// reads as the right edge emptying first (which feels like reverse).
import { computed, ref, watch } from "vue";

defineOptions({ inheritAttrs: false });

interface Step {
  /** Optional label shown under the dot. */
  label?: string;
}

interface Props {
  /** 1-based index of the active step. */
  current: number;
  /** Either pass `steps` for labelled dots, or `total` for plain numbers. */
  steps?: Step[];
  total?: number;
  /** Direction of the last navigation — caller hint, presentation only. */
  direction?: "forward" | "back";
  /** Pixel width of the connecting lines. Defaults to 56. */
  lineWidth?: number;
  /** Pixel diameter of each dot. Defaults to 32. */
  dotSize?: number;
}

const props = withDefaults(defineProps<Props>(), {
  steps: undefined,
  total: undefined,
  direction: "forward",
  lineWidth: 56,
  dotSize: 32,
});

const resolvedSteps = computed<Step[]>(() => {
  if (props.steps && props.steps.length > 0) return props.steps;
  const n = props.total ?? 0;
  return Array.from({ length: n }, () => ({}));
});

const items = computed(() =>
  resolvedSteps.value.map((step, i) => {
    const index = i + 1;
    let state: "past" | "current" | "future";
    if (index < props.current) state = "past";
    else if (index === props.current) state = "current";
    else state = "future";
    return { index, state, label: step.label };
  }),
);

const lineStyle = computed(() => ({ width: `${props.lineWidth}px` }));
const dotStyle = computed(() => ({
  width: `${props.dotSize}px`,
  height: `${props.dotSize}px`,
}));

// Bumped on every `current` change so the pop animation can replay on
// the same DOM element (CSS animations don't re-fire on a class change
// alone).
const bumpKey = ref(0);
watch(
  () => props.current,
  () => {
    bumpKey.value += 1;
  },
);
</script>

<template>
  <ol
    class="r-steps"
    :aria-label="`Step ${current} of ${items.length}`"
    :data-direction="direction"
  >
    <template v-for="(item, i) in items" :key="item.index">
      <li class="r-steps__item">
        <span
          class="r-steps__dot"
          :data-state="item.state"
          :data-bump="item.state === 'current' ? bumpKey : 0"
          :style="dotStyle"
        >
          <span class="r-steps__dot-num">{{ item.index }}</span>
        </span>
        <span v-if="item.label" class="r-steps__label">{{ item.label }}</span>
      </li>
      <li
        v-if="i < items.length - 1"
        class="r-steps__line"
        :data-active="items[i + 1]?.state !== 'future'"
        :style="lineStyle"
        aria-hidden="true"
      />
    </template>
  </ol>
</template>

<style scoped>
.r-steps {
  display: flex;
  align-items: center;
  gap: var(--r-space-2);
  list-style: none;
  margin: 0;
  padding: 0;
}

.r-steps__item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--r-space-1);
}

.r-steps__label {
  font-size: var(--r-font-size-xs);
  color: var(--r-color-fg-muted);
  white-space: nowrap;
}

/* ── Dots ────────────────────────────────────────────────────────── */
.r-steps__dot {
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: var(--r-font-size-sm);
  font-weight: var(--r-font-weight-semibold);
  border: 1px solid var(--r-color-border);
  background: var(--r-color-surface);
  color: var(--r-color-fg-muted);
  position: relative;
  transition:
    background 280ms cubic-bezier(0.2, 0.8, 0.2, 1),
    color 200ms ease,
    border-color 280ms cubic-bezier(0.2, 0.8, 0.2, 1),
    transform 280ms cubic-bezier(0.34, 1.56, 0.64, 1);
}

.r-steps__dot[data-state="past"] {
  background: var(--r-color-brand-primary);
  color: white;
  border-color: var(--r-color-brand-primary);
}

.r-steps__dot[data-state="current"] {
  background: var(--r-color-brand-primary);
  color: white;
  border-color: var(--r-color-brand-primary);
  transform: scale(1.1);
  animation: r-steps-pop 360ms cubic-bezier(0.34, 1.56, 0.64, 1);
}

.r-steps__dot[data-state="current"]::after {
  content: "";
  position: absolute;
  inset: -4px;
  border-radius: 50%;
  border: 2px solid var(--r-color-brand-primary);
  opacity: 0;
  animation: r-steps-pulse 1800ms ease-out infinite;
  pointer-events: none;
}

.r-steps__dot-num {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  line-height: 1;
}

@keyframes r-steps-pop {
  0% {
    transform: scale(0.7);
  }
  60% {
    transform: scale(1.18);
  }
  100% {
    transform: scale(1.1);
  }
}

@keyframes r-steps-pulse {
  0% {
    opacity: 0.6;
    transform: scale(1);
  }
  100% {
    opacity: 0;
    transform: scale(1.4);
  }
}

/* ── Lines ───────────────────────────────────────────────────────── */
.r-steps__line {
  height: 2px;
  border-radius: var(--r-radius-pill);
  background: var(--r-color-border);
  position: relative;
  overflow: hidden;
  align-self: center;
  /* Compensate for the dot's label so the line aligns with dot centres
     even when steps have labels under them. */
  transform: translateY(0);
}

/* The active fill animates scaleX from a fixed left origin so growing
   reads as "advance" and shrinking 1 → 0 reads as "the right side
   empties first" — matching the user's mental model of going back. */
.r-steps__line::after {
  content: "";
  position: absolute;
  inset: 0;
  background: var(--r-color-brand-primary);
  border-radius: inherit;
  transform-origin: left center;
  transform: scaleX(0);
  transition: transform 360ms cubic-bezier(0.2, 0.8, 0.2, 1);
}

.r-steps__line[data-active="true"]::after {
  transform: scaleX(1);
}

html[data-bp~="xs"] .r-steps__line {
  width: 32px !important;
}
</style>
