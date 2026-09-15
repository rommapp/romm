import { useFullscreen, type MaybeElementRef } from "@vueuse/core";
import { onScopeDispose, type ShallowRef } from "vue";
import { installFullscreenFallback } from "@/v2/utils/playerFullscreen";

export interface PlayerFullscreen {
  isFullscreen: ShallowRef<boolean>;
  enter: () => Promise<void>;
  exit: () => Promise<void>;
  toggle: () => Promise<void>;
}

/**
 * Fullscreen for a player stage, native where the platform has it.
 *
 * Players whose emulator library drives fullscreen itself (EmulatorJS, Ruffle,
 * js-dos) still call this without a target: the fallback patches the same
 * prototype the library reaches for, so their own controls work too.
 *
 * Args:
 *   target: the element to fullscreen. Omit for fallback installation only.
 */
export function usePlayerFullscreen(
  target?: MaybeElementRef,
): PlayerFullscreen {
  // Installed before useFullscreen resolves its methods, since on a platform
  // without the native API the fallback is what makes them exist.
  const removeFallback = installFullscreenFallback();
  onScopeDispose(removeFallback);

  const { isFullscreen, enter, exit, toggle } = useFullscreen(target);

  // A rejected request is a denial (permissions policy, or no user gesture),
  // not a fault to report: the stage simply stays windowed.
  const swallow = (run: () => Promise<void>) => () => run().catch(() => {});

  return {
    isFullscreen,
    enter: swallow(enter),
    exit: swallow(exit),
    toggle: swallow(toggle),
  };
}
