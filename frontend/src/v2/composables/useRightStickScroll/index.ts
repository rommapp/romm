// useRightStickScroll
//
// Lets a view's scroll container be driven by the right analog stick of
// any connected gamepad. Runs its own per-frame `getGamepads()` poll
// (cheap — one syscall per frame) and pushes the stick value past a
// deadzone into the element's scrollTop / scrollLeft. Independent of
// `useGamepad`'s left-stick → ArrowKey emulator, so the user can scroll
// the tab content with the right stick while D-pad / left stick keep
// navigating focusable elements.
//
// Tunables (constants — no consumer needs to override these yet):
//   * DEADZONE — ignore stick noise around the centre.
//   * SCROLL_PER_FRAME — pixels scrolled at full stick deflection per
//     frame; at 60fps full-up gives ~1500 px/s, which matches the feel
//     of "page down via dpad" without overshoot.
import { onBeforeUnmount, onMounted, type Ref } from "vue";

const DEADZONE = 0.15;
const SCROLL_PER_FRAME = 25;

export function useRightStickScroll(elRef: Ref<HTMLElement | null>) {
  let rafId = 0;
  let running = false;

  function tick() {
    const pads = navigator.getGamepads?.() ?? [];
    let dx = 0;
    let dy = 0;
    for (const p of pads) {
      if (!p) continue;
      // Standard mapping: right stick is axes 2 (X) and 3 (Y).
      const x = p.axes[2] ?? 0;
      const y = p.axes[3] ?? 0;
      // Latch the largest deflection across all pads so a multi-pad
      // setup still works without averaging the signals.
      if (Math.abs(x) > DEADZONE && Math.abs(x) > Math.abs(dx)) dx = x;
      if (Math.abs(y) > DEADZONE && Math.abs(y) > Math.abs(dy)) dy = y;
    }
    const el = elRef.value;
    if (el) {
      if (dy !== 0) el.scrollTop += dy * SCROLL_PER_FRAME;
      if (dx !== 0) el.scrollLeft += dx * SCROLL_PER_FRAME;
    }
    rafId = requestAnimationFrame(tick);
  }

  onMounted(() => {
    if (typeof navigator === "undefined" || !navigator.getGamepads) return;
    running = true;
    rafId = requestAnimationFrame(tick);
  });

  onBeforeUnmount(() => {
    if (running) {
      cancelAnimationFrame(rafId);
      running = false;
    }
  });
}
