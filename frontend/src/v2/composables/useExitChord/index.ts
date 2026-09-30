// The pad's way out of a stream, which mutes useGamepad (B included) while it
// owns the controller. The hold outlasts a game's own Select+Start binds.
import { useIntervalFn } from "@vueuse/core";
import { toValue, watch, type MaybeRefOrGetter } from "vue";
import { isUsablePad, PAD_BUTTON } from "@/v2/composables/useGamepad";

const HOLD_MS = 1500;
// Coarse on purpose: this shares the thread compositing the stream.
const POLL_MS = 100;

export function useExitChord(
  /** Whether the session owns the pad, and so whether to listen at all. */
  active: MaybeRefOrGetter<boolean>,
  /** Called once per completed hold; the caller dedupes an open dialog. */
  onChord: () => void,
): void {
  let heldSince = 0;
  // Set once a hold fires, so a chord still held after the dialog is cancelled
  // waits for a release instead of reopening it.
  let fired = false;

  function poll(): void {
    const pads = navigator.getGamepads ? navigator.getGamepads() : [];
    const held = Array.from(pads).some(
      (pad) =>
        // Other mappings don't guarantee the Back/Start indices.
        isUsablePad(pad) &&
        pad.mapping === "standard" &&
        pad.buttons[PAD_BUTTON.back]?.pressed &&
        pad.buttons[PAD_BUTTON.start]?.pressed,
    );
    const now = performance.now();
    if (!held) {
      heldSince = 0;
      fired = false;
    } else if (fired) {
      return;
    } else if (!heldSince) {
      heldSince = now;
    } else if (now - heldSince >= HOLD_MS) {
      fired = true;
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
        fired = false;
      }
    },
    { immediate: true },
  );
}
