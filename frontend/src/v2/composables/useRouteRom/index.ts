// useRouteRom: the DetailedRom the route's `:rom` param names. Keyed on the
// committed route, so a navigation that prefetches the next game in a guard
// leaves this page on its own until the route actually changes.
import { computed, type ComputedRef } from "vue";
import { type RouteLocationNormalizedLoaded, useRoute } from "vue-router";
import storeRoms, { type DetailedRom } from "@/stores/roms";

/** The ROM id in `route`'s `:rom` param, or null on a route without one. */
export function romIdFromRoute(
  route: Pick<RouteLocationNormalizedLoaded, "params">,
): number | null {
  const raw = route.params.rom;
  const id = typeof raw === "string" ? Number(raw) : NaN;
  return Number.isInteger(id) ? id : null;
}

export function useRouteRom(): ComputedRef<DetailedRom | null> {
  const route = useRoute();
  const romsStore = storeRoms();
  return computed(() => {
    const id = romIdFromRoute(route);
    return id === null ? null : romsStore.getDetailedRom(id);
  });
}
