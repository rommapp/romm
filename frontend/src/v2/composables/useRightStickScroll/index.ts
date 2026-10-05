// useRightStickScroll
//
// Lets a view's scroll container be driven by the right analog stick of
// any connected gamepad. Reads the stick each frame (`readRightStick`) and
// pushes it past a deadzone into the element's scrollTop / scrollLeft.
// Independent of `useGamepad`'s left-stick → ArrowKey emulator, so the
// user can scroll the tab content with the right stick while D-pad / left
// stick keep navigating focusable elements.
//
// Tunables (constants: no consumer needs to override these yet):
//   * DEADZONE: ignore stick noise around the centre.
//   * SCROLL_PER_FRAME: pixels scrolled at full stick deflection per
//     frame; at 60fps full-up gives ~1500 px/s, which matches the feel
//     of "page down via dpad" without overshoot.
import { useRafFn } from "@vueuse/core";
import type { Ref } from "vue";
import { readRightStick } from "@/v2/utils/gamepad";

const DEADZONE = 0.15;
const SCROLL_PER_FRAME = 25;

export function useRightStickScroll(elRef: Ref<HTMLElement | null>) {
  if (typeof navigator === "undefined" || !navigator.getGamepads) return;

  useRafFn(() => {
    const el = elRef.value;
    if (!el) return;
    const { x, y } = readRightStick();
    if (Math.abs(y) > DEADZONE) el.scrollTop += y * SCROLL_PER_FRAME;
    if (Math.abs(x) > DEADZONE) el.scrollLeft += x * SCROLL_PER_FRAME;
  });
}
