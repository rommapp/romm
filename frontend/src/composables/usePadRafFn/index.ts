import { useEventListener, useIntervalFn, useRafFn } from "@vueuse/core";
import { hasUsablePad } from "@/utils/gamepad";

// Catches a pad some webviews expose without firing gamepadconnected.
const IDLE_PROBE_MS = 1000;

/** Runs `fn` every frame only while a pad is connected (Chrome reports one
 * after its first press). */
export function usePadRafFn(fn: () => void): void {
  const raf = useRafFn(fn, { immediate: hasUsablePad() });
  const probe = useIntervalFn(
    () => {
      if (hasUsablePad()) resume();
    },
    IDLE_PROBE_MS,
    { immediate: !raf.isActive.value },
  );

  function resume() {
    probe.pause();
    raf.resume();
  }

  useEventListener(window, "gamepadconnected", resume);
  useEventListener(window, "gamepaddisconnected", () => {
    if (hasUsablePad()) return;
    raf.pause();
    probe.resume();
  });
}
