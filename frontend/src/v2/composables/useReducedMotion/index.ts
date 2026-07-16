// useReducedMotion — reactive `prefers-reduced-motion: reduce` as a boolean.
//
// Single source for the OS reduced-motion signal so every consumer stops
// hand-rolling `window.matchMedia("(prefers-reduced-motion: reduce)")`. Backed
// by one module-level `useMediaQuery` listener shared across callers (same
// pattern as useBreakpoint), so the value is reactive and flips live if the
// user changes the OS setting while the app is open.
//
// vueuse ships `usePreferredReducedMotion`, but it returns a
// 'reduce' | 'no-preference' string; this exposes the plain boolean every
// call site already wants (`if (reducedMotion.value)`). Generic and
// domain-free, so primitives (RExpandTransition, RBox3D) may use it too.
import { useMediaQuery } from "@vueuse/core";
import type { Ref } from "vue";

const reduced = useMediaQuery("(prefers-reduced-motion: reduce)");

export function useReducedMotion(): Ref<boolean> {
  return reduced;
}
