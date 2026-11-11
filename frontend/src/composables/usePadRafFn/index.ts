import { useEventListener, useRafFn } from "@vueuse/core";
import { hasUsablePad } from "@/utils/gamepad";

/** Runs `fn` every frame only while a pad is connected (Chrome reports one
 * after its first press). */
export function usePadRafFn(fn: () => void): void {
  const raf = useRafFn(fn, { immediate: hasUsablePad() });
  useEventListener(window, "gamepadconnected", raf.resume);
  useEventListener(window, "gamepaddisconnected", () => {
    if (!hasUsablePad()) raf.pause();
  });
}
