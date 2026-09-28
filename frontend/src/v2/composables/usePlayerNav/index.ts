// usePlayerNav — the two back links every v2 player view carries. The route id
// is used rather than the hero's, so the links work during the seed window.
import { computed, type ComputedRef } from "vue";
import type { RouteLocationRaw } from "vue-router";
import { ROUTES } from "@/plugins/router";

export function usePlayerNav(
  romId: number,
  platformId: () => number | null | undefined,
): {
  romRoute: RouteLocationRaw;
  /** Undefined until the hero says which platform the rom belongs to. */
  platformRoute: ComputedRef<RouteLocationRaw | undefined>;
} {
  const romRoute: RouteLocationRaw = {
    name: ROUTES.ROM,
    params: { rom: romId },
  };

  const platformRoute = computed<RouteLocationRaw | undefined>(() => {
    const platform = platformId();
    if (platform == null) return undefined;
    return { name: ROUTES.PLATFORM, params: { platform } };
  });

  return { romRoute, platformRoute };
}
