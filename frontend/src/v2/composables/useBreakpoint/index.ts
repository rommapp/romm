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
import { useMediaQuery } from "@vueuse/core";
import type { Ref } from "vue";

const xs = useMediaQuery("(max-width: 599.98px)");
const smAndUp = useMediaQuery("(min-width: 600px)");
const mdAndUp = useMediaQuery("(min-width: 960px)");
const lgAndUp = useMediaQuery("(min-width: 1280px)");
const xlAndUp = useMediaQuery("(min-width: 1920px)");

export function useBreakpoint(): {
  xs: Ref<boolean>;
  smAndUp: Ref<boolean>;
  mdAndUp: Ref<boolean>;
  lgAndUp: Ref<boolean>;
  xlAndUp: Ref<boolean>;
} {
  return { xs, smAndUp, mdAndUp, lgAndUp, xlAndUp };
}
