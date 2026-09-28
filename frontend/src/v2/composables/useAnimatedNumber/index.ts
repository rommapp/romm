// useAnimatedNumber: a count that rolls up to its new value instead of
// snapping to it, so a number that changed is a number you noticed.
//
// Reduced motion comes from `useReducedMotion` rather than the global CSS
// guard, which cannot reach a ref driven by requestAnimationFrame.
import { onScopeDispose, ref, watch, type Ref } from "vue";
import { useReducedMotion } from "@/v2/composables/useReducedMotion";
import { motion } from "@/v2/tokens";
import { tween } from "@/v2/utils/tween";

type Source = string | number | null | undefined;

interface Options {
  /** Roll duration in ms. Defaults to the `slow` motion token. */
  duration?: number;
  /** Decimals kept on the in-between frames (the final value lands exact). */
  decimals?: number;
}

/**
 * Follows `source`, rolling through the numbers on the way. Anything already
 * formatted (a size, a date, a range) passes straight through, so a caller
 * can hand over a value it doesn't have to classify first.
 */
export function useAnimatedNumber(
  source: () => Source,
  options: Options = {},
): Ref<string | number | null> {
  const { enabled: reducedMotion } = useReducedMotion();
  const duration = options.duration ?? parseInt(motion.slow, 10);
  const decimals = options.decimals ?? 0;
  const display = ref<string | number | null>(null);
  let cancel: (() => void) | null = null;

  function stop() {
    cancel?.();
    cancel = null;
  }

  watch(
    source,
    (target) => {
      stop();
      // Nothing to roll through: a missing value is a dash at the call site,
      // and a formatted one is already what the caller wants painted.
      if (target == null || typeof target === "string") {
        display.value = target ?? null;
        return;
      }
      // The first value rolls up from zero, which is the whole point of the
      // effect: a count that arrives is a count you watch land.
      const from = typeof display.value === "number" ? display.value : 0;
      if (from === target) {
        display.value = target;
        return;
      }
      cancel = tween({
        from,
        to: target,
        durationMs: reducedMotion.value ? 0 : duration,
        // Rounding is cosmetic, for the frames in between: a raw tween value
        // like 1567.4972637 would paint in full and widen the layout mid-roll.
        onUpdate: (value) => (display.value = Number(value.toFixed(decimals))),
        // The value it lands on is the caller's, decimals and all.
        onDone: () => (display.value = target),
      });
    },
    { immediate: true },
  );

  onScopeDispose(stop);

  return display;
}
