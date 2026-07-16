// useReducedEffects — singleton toggle for a low-power "reduced effects" mode.
//
// When on, the app drops GPU-heavy decorative visuals that are cheap on a
// desktop GPU but punishing on weak hardware (TV boxes, older phones): the
// full-viewport background blur and the per-cover blur-up reveal. It leaves
// layout, colors and content untouched, so the only difference is that the
// backdrop is unblurred and covers fade in without the bloom.
//
// This is intentionally a per-device localStorage flag (not a backend-synced
// UI setting): whether effects are too heavy depends on the machine RomM is
// being viewed on, not on the user's account. Same singleton-ref rationale as
// useCrtMode — vueuse's useLocalStorage makes an independent ref per call, so
// we create it once here and share the instance.
import { useLocalStorage } from "@vueuse/core";

const enabled = useLocalStorage("settings.v2.reducedEffects", false);

export function useReducedEffects() {
  /** Flip reduced-effects mode and return the new state (true = now on). */
  function toggle(): boolean {
    enabled.value = !enabled.value;
    return enabled.value;
  }

  return { enabled, toggle };
}
