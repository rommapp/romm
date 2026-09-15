// usePlayerFullscreen — fullscreen for a player stage, native where the
// platform has it and emulated where it does not.
import { useFullscreen, type MaybeElementRef } from "@vueuse/core";
import { type ShallowRef } from "vue";
import { useFullscreenFallback } from "@/v2/composables/useFullscreenFallback";

// A rejected request is a denial (permissions policy, or no user gesture),
// not a fault to report: the stage simply stays windowed.
const swallowDenial = (run: () => Promise<void>) => () => run().catch(() => {});

// A failed exit is not benign: callers exit before opening a body-teleported
// dialog, which would then be painted over by the fullscreen stage.
const reportFailure = (run: () => Promise<void>) => () =>
  run().catch((error: unknown) => {
    console.error("Failed to exit fullscreen", error);
  });

/** Fullscreen controls for `target`. */
export function usePlayerFullscreen(target: MaybeElementRef): {
  isFullscreen: ShallowRef<boolean>;
  enter: () => Promise<void>;
  exit: () => Promise<void>;
  toggle: () => Promise<void>;
} {
  // Before useFullscreen resolves its methods: where the native API is absent
  // the fallback is what makes them exist.
  useFullscreenFallback();

  const { isFullscreen, enter, exit, toggle } = useFullscreen(target);

  return {
    isFullscreen,
    enter: swallowDenial(enter),
    exit: reportFailure(exit),
    toggle: swallowDenial(toggle),
  };
}
