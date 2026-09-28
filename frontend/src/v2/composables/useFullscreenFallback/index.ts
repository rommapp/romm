// useFullscreenFallback — installs the emulated Fullscreen API for this scope
// on platforms that have none for elements.
import { onScopeDispose } from "vue";
import { installFullscreenFallback } from "@/v2/utils/playerFullscreen";

// Refcounted because the patch is process-global while its callers are scoped:
// overlapping consumers would otherwise stack private patch layers.
let consumers = 0;
let removeFallback: (() => void) | null = null;

/**
 * Patches the Fullscreen API for this scope where the platform lacks it.
 *
 * Players whose emulator library drives fullscreen itself need only this: the
 * fallback patches the same prototype the library reaches for.
 */
export function useFullscreenFallback(): void {
  if (consumers++ === 0) removeFallback = installFullscreenFallback();

  onScopeDispose(() => {
    if (--consumers > 0) return;
    removeFallback?.();
    removeFallback = null;
  });
}
