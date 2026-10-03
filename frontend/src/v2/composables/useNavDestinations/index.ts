// useNavDestinations: single source of truth for the four primary
// content destinations (Home / Platforms / Collections / Search) and the
// route-path → active-tab derivation. Shared by `AppNav` (desktop top
// pill) and `BottomNav` (mobile bottom bar) so the two never drift in
// labels, icons, ordering, or active-state logic.
//
// Highlighting is derived from `route.path` (not route names) so gallery
// subroutes (e.g. `/rom/:id` reached from a platform) still light up
// their parent destination.
import { computed } from "vue";
import type { ComputedRef } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute } from "vue-router";

export type NavDestinationId = "home" | "platforms" | "collections" | "search";

export interface NavDestination {
  id: NavDestinationId;
  label: string;
  // Mirrors `label` so the icon-only variants (xs top pill, bottom bar)
  // still name each link to screen readers / focus rings.
  ariaLabel: string;
  icon: string;
  to: string;
}

// Tab order and targets. useGamepad's LB/RB cycles through the same list.
export const NAV_TARGETS: readonly { id: NavDestinationId; to: string }[] = [
  { id: "home", to: "/" },
  { id: "platforms", to: "/platforms" },
  { id: "collections", to: "/collections" },
  { id: "search", to: "/search" },
];

const NAV_META: Record<NavDestinationId, { labelKey: string; icon: string }> = {
  home: { labelKey: "common.home", icon: "mdi-home-outline" },
  platforms: { labelKey: "common.platforms", icon: "mdi-controller" },
  // Same glyph GameCard uses for its "add to collection" action:
  // keeps the icon stable across every generic "Collections" surface.
  collections: { labelKey: "common.collections", icon: "mdi-bookmark-outline" },
  search: { labelKey: "common.search", icon: "mdi-magnify" },
};

/** The destination `path` belongs to; gallery sub-routes count as their parent. */
export function navDestinationAt(path: string): NavDestinationId | null {
  if (path === "/") return "home";
  if (path.startsWith("/platform")) return "platforms";
  if (path.startsWith("/collection")) return "collections";
  if (path.startsWith("/search")) return "search";
  return null;
}

export function useNavDestinations(): {
  destinations: ComputedRef<NavDestination[]>;
  activeId: ComputedRef<NavDestinationId | null>;
} {
  const { t } = useI18n();
  const route = useRoute();

  const destinations = computed<NavDestination[]>(() =>
    NAV_TARGETS.map(({ id, to }) => {
      const { labelKey, icon } = NAV_META[id];
      const label = t(labelKey);
      return { id, label, ariaLabel: label, icon, to };
    }),
  );

  const activeId = computed(() => navDestinationAt(route.path));

  return { destinations, activeId };
}
