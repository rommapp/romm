// usePlayFocus
//
// Lands focus on a player's Play CTA. A player's setup screen has no spatial
// navigation for a d-pad to walk, so the CTA is the only way a gamepad gets
// into the view at all (#4397): claim it once the screen is ready, again when
// the user picks up a pad, and again when a running game hands the screen
// back.
import { nextTick, toValue, watch, type MaybeRefOrGetter } from "vue";
import { useInputModality } from "@/v2/composables/useInputModality";
import { shouldClaimFocusOnModality } from "@/v2/utils/autofocus";

export function usePlayFocus(
  /** CSS selector for the CTA. A query survives the button's lazy render
   *  where a template ref taken at setup would not. */
  selector: string,
  ready: MaybeRefOrGetter<boolean>,
  running: MaybeRefOrGetter<boolean>,
) {
  const { modality } = useInputModality();

  function focusPlay() {
    document
      .querySelector<HTMLElement>(selector)
      ?.focus({ preventScroll: true });
  }

  // The CTA is disabled until the screen is ready and a disabled button can't
  // take focus, so readiness is part of what this watches.
  watch(
    [() => toValue(ready), modality],
    ([isReady]) => {
      if (!isReady || toValue(running)) return;
      if (
        !shouldClaimFocusOnModality(
          modality.value,
          document.activeElement,
          document.body,
        )
      ) {
        return;
      }
      // Re-checked on the tick the CTA is actually in the DOM: a stored
      // launch intent can start the game between the two.
      void nextTick(() => {
        if (!toValue(running)) focusPlay();
      });
    },
    { immediate: true },
  );

  // Exiting a game leaves the page unfocused, so a play-quit-play loop would
  // otherwise need the mouse to start over.
  watch(
    () => toValue(running),
    (now, before) => {
      if (before && !now) void nextTick(focusPlay);
    },
  );
}
