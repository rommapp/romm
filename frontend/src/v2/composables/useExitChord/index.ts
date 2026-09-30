// useExitChord: the pad's way out of a streaming session. A stream mutes
// useGamepad for as long as it owns the controller (launch included), so B
// can no longer reach the route-leave guard; holding Select+Start is read
// straight from the Gamepad API instead. Polling through the launch keeps
// the exit reachable by pad if a claim hangs.
//
// The 1.5s hold filters out anything a game itself binds to Select+Start.
// Only standard-mapped pads participate: elsewhere indices 8/9 are not
// guaranteed to be Select+Start.
import { useIntervalFn } from "@vueuse/core";
import { toValue, watch, type MaybeRefOrGetter } from "vue";

const HOLD_MS = 1500;
// A 1.5s hold needs nowhere near frame resolution, and this runs on the thread
// compositing the stream for as long as the session lasts.
const POLL_MS = 100;

export function useExitChord(
  /** Whether the session owns the pad, and so whether to listen at all. */
  active: MaybeRefOrGetter<boolean>,
  /** Called once per completed hold; the caller dedupes an open dialog. */
  onChord: () => void,
): void {
  let heldSince = 0;

  function poll(): void {
    const pads = navigator.getGamepads ? navigator.getGamepads() : [];
    const held = Array.from(pads).some(
      (pad) =>
        pad &&
        pad.mapping === "standard" &&
        pad.buttons[8]?.pressed &&
        pad.buttons[9]?.pressed,
    );
    const now = performance.now();
    if (!held) {
      heldSince = 0;
    } else if (!heldSince) {
      heldSince = now;
    } else if (now - heldSince >= HOLD_MS) {
      heldSince = 0;
      onChord();
    }
  }

  const { pause, resume } = useIntervalFn(poll, POLL_MS, { immediate: false });

  watch(
    () => toValue(active),
    (on) => {
      if (on) {
        resume();
      } else {
        pause();
        heldSince = 0;
      }
    },
    { immediate: true },
  );
}
