// useAnimatedNumber — a count that rolls up to its new value instead of
// snapping to it, so a number that changed is a number you noticed.
//
// Ported from the same composable in Berserk (itself from Turtletrips), with
// two changes for this codebase: the duration comes from the motion tokens,
// and reduced motion is read through `useReducedMotion`, which also honours
// the in-app setting — the global CSS guard can't reach a ref driven by
// requestAnimationFrame.
import { onScopeDispose, ref, watch, type Ref } from "vue";
import { useReducedMotion } from "@/v2/composables/useReducedMotion";
import { motion } from "@/v2/tokens";

interface Options {
  /** Roll duration in ms. Defaults to the `slow` motion token. */
  duration?: number;
  /** Decimals kept on the in-between frames (the final value lands exact). */
  decimals?: number;
}

export function useAnimatedNumber(
  source: () => number | null | undefined,
  options: Options = {},
): Ref<number | null> {
  const { enabled: reducedMotion } = useReducedMotion();
  const duration = options.duration ?? parseInt(motion.slow, 10);
  const decimals = options.decimals ?? 0;
  const display = ref<number | null>(null);
  let frame: number | null = null;

  function stop() {
    if (frame !== null) cancelAnimationFrame(frame);
    frame = null;
  }

  function animate(from: number, to: number) {
    if (duration <= 0 || reducedMotion.value) {
      display.value = to;
      return;
    }
    const start = performance.now();
    const step = (now: number) => {
      const t = Math.min(1, (now - start) / duration);
      const eased = 1 - (1 - t) ** 3;
      // Rounding is cosmetic, for the frames in between: a raw tween value
      // like 1567.4972637 would paint in full and widen the layout mid-roll.
      display.value =
        t < 1 ? Number((from + (to - from) * eased).toFixed(decimals)) : to;
      frame = t < 1 ? requestAnimationFrame(step) : null;
    };
    frame = requestAnimationFrame(step);
  }

  watch(
    source,
    (target) => {
      stop();
      // A missing value is a dash at the call site, not a number to roll to.
      if (target == null) {
        display.value = null;
        return;
      }
      // The first value rolls up from zero, which is the whole point of the
      // effect: a count that arrives is a count you watch land.
      const from = display.value ?? 0;
      if (from === target) {
        display.value = target;
        return;
      }
      animate(from, target);
    },
    { immediate: true },
  );

  onScopeDispose(stop);

  return display;
}
