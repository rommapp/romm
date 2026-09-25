// useCrtMode — singleton toggle for the cosmetic "CRT mode" shader.
//
// CRT mode is a purely visual easter egg: when on, a persistent full-screen
// scanline / vignette / flicker / glitch overlay (CrtOverlay.vue) makes RomM
// look like it is running on an old cathode-ray tube, and toggling it ON
// fires the one-shot power-on warm-up flash (CrtWarmup.vue).
//
// State is persisted in localStorage and shared across components through a
// single module-level ref — same rationale as `useUiVersion`: vueuse's
// useLocalStorage creates an independent ref per call (shared storage, not
// shared reactivity within a tab), so we create it once here and everyone
// imports the same instance.
import { useLocalStorage } from "@vueuse/core";
import { computed } from "vue";
import { useReducedMotion } from "@/v2/composables/useReducedMotion";

const stored = useLocalStorage("settings.v2.crtMode", false);
const { enabled: reducedMotion, toggle: toggleReducedMotion } =
  useReducedMotion();

// Reduced motion breaks the overlay's endless animations, so it hides CRT
// without erasing the saved choice, and turning CRT on turns it off.
const enabled = computed<boolean>({
  get: () => stored.value && !reducedMotion.value,
  set: (on) => {
    stored.value = on;
    if (on && reducedMotion.value) toggleReducedMotion();
  },
});

export function useCrtMode() {
  /** Flip CRT mode and return the new state (true = now on). */
  function toggle(): boolean {
    enabled.value = !enabled.value;
    return enabled.value;
  }

  return { enabled, toggle };
}
