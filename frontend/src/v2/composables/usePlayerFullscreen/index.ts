// usePlayerFullscreen — fullscreen for a player stage, native where the
// platform has it and emulated where it does not.
import { useFullscreen, type MaybeElementRef } from "@vueuse/core";
import { onScopeDispose, type ShallowRef } from "vue";
import { installFullscreenFallback } from "@/v2/utils/playerFullscreen";

// Refcounted because the patch is process-global while its callers are scoped:
// overlapping consumers would otherwise stack private patch layers.
let consumers = 0;
let removeFallback: (() => void) | null = null;

/** Patches the Fullscreen API for this scope where the platform lacks it. */
export function useFullscreenFallback(): void {
  if (consumers++ === 0) removeFallback = installFullscreenFallback();

  onScopeDispose(() => {
    if (--consumers > 0) return;
    removeFallback?.();
    removeFallback = null;
  });
}

// A rejected request is a denial (permissions policy, or no user gesture),
// not a fault to report: the stage simply stays windowed.
const swallow = (run: () => Promise<void>) => () => run().catch(() => {});

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
    enter: swallow(enter),
    exit: swallow(exit),
    toggle: swallow(toggle),
  };
}
