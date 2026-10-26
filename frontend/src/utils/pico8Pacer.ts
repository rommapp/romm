// Frame pacing for the PICO-8 player, kept apart from the view so the
// catch-up rules are unit-testable without a canvas or a rAF loop.

/** Longest gap a single tick may carry, so a backgrounded tab does not spin. */
const MAX_ELAPSED_MS = 250;
/** Emulated frames one tick may run before it must paint. */
const MAX_CATCH_UP = 3;

export interface Pico8Pacer {
  /** Anchor the clock, priming one frame so the first tick renders. */
  reset: (now: number) => void;
  /**
   * Advance the clock.
   *
   * @param now A monotonic timestamp in milliseconds.
   * @returns How many emulated frames to run before painting.
   */
  tick: (now: number) => number;
}

/**
 * Build a pacer for a cart's target frame rate.
 *
 * @param frameRate Frames per second the cart asks for (PICO-8 uses 30 or 60).
 * @returns The pacer.
 */
export function createPico8Pacer(frameRate: number): Pico8Pacer {
  const frameDuration = 1000 / frameRate;
  let last = 0;
  let accumulator = 0;

  return {
    reset(now) {
      last = now;
      accumulator = frameDuration;
    },
    tick(now) {
      accumulator += Math.min(now - last, MAX_ELAPSED_MS);
      last = now;

      let steps = 0;
      while (accumulator >= frameDuration && steps < MAX_CATCH_UP) {
        accumulator -= frameDuration;
        steps += 1;
      }
      // Drop debt beyond the cap instead of carrying it into the next tick,
      // which would keep the loop permanently behind after one long stall.
      if (steps === MAX_CATCH_UP) accumulator = 0;
      return steps;
    },
  };
}
