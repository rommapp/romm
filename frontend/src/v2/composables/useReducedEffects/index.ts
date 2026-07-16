// useReducedEffects — singleton toggle for a low-power "reduced effects" mode.
//
// When on, the app drops GPU-heavy decorative visuals that are cheap on a
// desktop GPU but punishing on weak hardware (TV boxes, older phones): the
// full-viewport background blur and the per-cover blur-up reveal. It leaves
// layout, colors and content untouched, so the only difference is that the
// backdrop is unblurred and covers fade in without the bloom.
//
// Default: follow the OS `prefers-reduced-motion` setting. Someone who asks
// their system to reduce motion generally wants fewer heavy effects too, so
// this mode starts on for them without any per-app opt-in. The Settings
// toggle records an explicit choice that overrides the system default from
// then on (a null override means "no explicit choice, follow the system").
//
// Per-device (not backend-synced): whether effects are too heavy depends on
// the machine RomM is viewed on, not the user's account. Same singleton-ref
// rationale as useCrtMode — vueuse's useLocalStorage / useMediaQuery make an
// independent ref per call, so we create them once here and share.
import { useLocalStorage, useMediaQuery } from "@vueuse/core";
import { computed } from "vue";

// null = no explicit choice yet (follow the system); true/false = user
// override. An explicit serializer is required: with a null default vueuse
// would fall back to its identity ("any") serializer and read persisted
// booleans back as strings.
const override = useLocalStorage<boolean | null>(
  "settings.v2.reducedEffects",
  null,
  {
    serializer: {
      read: (v) => (v === "true" ? true : v === "false" ? false : null),
      write: (v) => String(v),
    },
  },
);
const prefersReducedMotion = useMediaQuery("(prefers-reduced-motion: reduce)");

const enabled = computed<boolean>({
  get: () => override.value ?? prefersReducedMotion.value,
  set: (value) => {
    override.value = value;
  },
});

export function useReducedEffects() {
  /** Flip reduced-effects mode and return the new state (true = now on).
   * Writing through `enabled` records an explicit override. */
  function toggle(): boolean {
    enabled.value = !enabled.value;
    return enabled.value;
  }

  return { enabled, toggle };
}
