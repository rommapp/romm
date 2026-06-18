// useBreakpoint — reactive responsive breakpoints with the same names
// used at call sites (`xs`, `smAndUp`, `mdAndUp`, `lgAndUp`, `xlAndUp`).
// Backed by `useMediaQuery` so each ref flips on viewport change without
// a manual resize listener.
//
// Thresholds match the standard Material breakpoints (xs <600,
// sm 600-959, md 960-1279, lg 1280-1919, xl ≥1920) so a swap from any
// previous library reads identically.
//
// Module-level singletons — the media query listeners attach once and
// every consumer shares them. Composable returns the refs by name.
//
// `installBreakpointAttribute()` (called once from the root layout)
// mirrors the active breakpoints onto `data-bp` on `<html>` as a
// space-separated list — e.g. `data-bp="sm-and-up md-and-up"` at a
// 1024px viewport. CSS consumes the attribute with `~=` selectors:
//   html[data-bp~="xs"] .my-class { … }   // mobile only
//   html[data-bp~="sm-and-up"] .x { … }   // tablet+ (≥ 600)
// keeping breakpoint values in this single file instead of dozens of
// `@media` queries across the codebase. Mirrors the `data-input`
// pattern installed by `useInputModality`.
import { useMediaQuery } from "@vueuse/core";
import { onBeforeUnmount, watch } from "vue";
import type { Ref } from "vue";

const xs = useMediaQuery("(max-width: 599.98px)");
const smAndUp = useMediaQuery("(min-width: 600px)");
const smAndDown = useMediaQuery("(max-width: 959.98px)");
const mdAndUp = useMediaQuery("(min-width: 960px)");
const mdAndDown = useMediaQuery("(max-width: 1279.98px)");
const lgAndUp = useMediaQuery("(min-width: 1280px)");
const lgAndDown = useMediaQuery("(max-width: 1919.98px)");
const xlAndUp = useMediaQuery("(min-width: 1920px)");

export function useBreakpoint(): {
  xs: Ref<boolean>;
  smAndUp: Ref<boolean>;
  smAndDown: Ref<boolean>;
  mdAndUp: Ref<boolean>;
  mdAndDown: Ref<boolean>;
  lgAndUp: Ref<boolean>;
  lgAndDown: Ref<boolean>;
  xlAndUp: Ref<boolean>;
} {
  return {
    xs,
    smAndUp,
    smAndDown,
    mdAndUp,
    mdAndDown,
    lgAndUp,
    lgAndDown,
    xlAndUp,
  };
}

// Kebab tokens written into `data-bp`. Order is ascending threshold (xs
// → xl) so the attribute reads predictably in devtools — e.g. an xl
// viewport always shows the same token order, not a randomly-shuffled
// list. The `*-and-down` siblings live alongside their `*-and-up` peers
// so both directions of a viewport range are addressable with one
// `~=` selector instead of `:not(...)` negation.
const TOKENS: ReadonlyArray<readonly [Ref<boolean>, string]> = [
  [xs, "xs"],
  [smAndUp, "sm-and-up"],
  [smAndDown, "sm-and-down"],
  [mdAndUp, "md-and-up"],
  [mdAndDown, "md-and-down"],
  [lgAndUp, "lg-and-up"],
  [lgAndDown, "lg-and-down"],
  [xlAndUp, "xl-and-up"],
];

let installed = false;

function applyAttribute() {
  if (typeof document === "undefined") return;
  const active = TOKENS.filter(([ref]) => ref.value).map(([, name]) => name);
  document.documentElement.dataset.bp = active.join(" ");
}

/** Install once at the root layout. Mirrors the active breakpoints onto
 *  `<html data-bp="…">` so scoped styles can read the viewport without
 *  hardcoding `@media` values. Subsequent calls are no-ops. */
export function installBreakpointAttribute(): void {
  if (installed) return;
  installed = true;

  applyAttribute();
  const stop = watch(
    TOKENS.map(([ref]) => ref),
    applyAttribute,
  );

  onBeforeUnmount(() => {
    stop();
    installed = false;
  });
}
