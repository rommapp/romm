import type { RouteLocationNormalized, RouteLocationRaw } from "vue-router";
import { ROUTES } from "@/plugins/routeNames";

/**
 * Where a v1 console route lands in the v2 UI, which has no console mode: the
 * same page in the main UI, so a bookmark or a console link never boots the v1
 * console player.
 *
 * Returns:
 *   The v2 location, or null for a route that is not a console one.
 */
export function v2RouteForConsole(
  to: Pick<RouteLocationNormalized, "name" | "params" | "query">,
): RouteLocationRaw | null {
  const { params, query } = to;
  switch (to.name) {
    case ROUTES.CONSOLE_HOME:
      return { name: ROUTES.HOME };
    case ROUTES.CONSOLE_PLATFORM:
      return { name: ROUTES.PLATFORM, params: { platform: params.id } };
    case ROUTES.CONSOLE_COLLECTION:
      return { name: ROUTES.COLLECTION, params: { collection: params.id } };
    case ROUTES.CONSOLE_SMART_COLLECTION:
      return {
        name: ROUTES.SMART_COLLECTION,
        params: { collection: params.id },
      };
    case ROUTES.CONSOLE_VIRTUAL_COLLECTION:
      return {
        name: ROUTES.VIRTUAL_COLLECTION,
        params: { collection: params.id },
      };
    case ROUTES.CONSOLE_ROM:
      return { name: ROUTES.ROM, params: { rom: params.rom } };
    case ROUTES.CONSOLE_PLAY:
      return { name: ROUTES.EMULATORJS, params: { rom: params.rom }, query };
    default:
      return null;
  }
}
