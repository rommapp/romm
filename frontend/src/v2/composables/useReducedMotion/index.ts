// useReducedMotion — the single "reduce motion / effects" control.
//
// Combines the OS `prefers-reduced-motion` signal with a per-device user
// override into one reactive `enabled` boolean, plus a `toggle()`:
//   * enabled = override ?? OS preference
//   * no explicit choice (override null) → follow the OS setting live
//   * an explicit choice wins from then on (decoupled from the OS)
//
// It drives everything motion- and GPU-effect-related: the `r-v2-reduced-motion`
// root class (background blur + the global animation/transition neutralize in
// global.css, cover blur-up in GameCover), plus the JS-driven motion gates that
// CSS can't reach (the cover CD-spin in useCoverAnimation, view-transition
// morphs, RExpandTransition, RBox3D's idle drift). One hook, one Settings
// toggle, one source of truth.
//
// Per-device (localStorage, not backend-synced): whether motion/effects are
// too heavy depends on the machine RomM is viewed on, not the account. Same
// singleton rationale as useBreakpoint — the media query listener attaches once
// at module load and every consumer shares the reactive refs.
import { useLocalStorage, useMediaQuery } from "@vueuse/core";
import { computed, type ComputedRef } from "vue";

// null = no explicit choice yet (follow the system); true/false = user
// override. An explicit serializer is required: with a null default vueuse
// would fall back to its identity ("any") serializer and read persisted
// booleans back as strings.
const override = useLocalStorage<boolean | null>(
  "settings.v2.reducedMotion",
  null,
  {
    serializer: {
      read: (v) => (v === "true" ? true : v === "false" ? false : null),
      write: (v) => String(v),
    },
  },
);

const systemPreference = useMediaQuery("(prefers-reduced-motion: reduce)");

const enabled = computed<boolean>({
  get: () => override.value ?? systemPreference.value,
  set: (value) => {
    override.value = value;
  },
});

export function useReducedMotion(): {
  enabled: ComputedRef<boolean>;
  toggle: () => boolean;
} {
  /** Flip reduced-motion mode and return the new state (true = now on).
   * Writing through `enabled` records an explicit override. */
  function toggle(): boolean {
    enabled.value = !enabled.value;
    return enabled.value;
  }

  return { enabled: enabled as ComputedRef<boolean>, toggle };
}
