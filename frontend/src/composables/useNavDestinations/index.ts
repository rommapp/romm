// useNavDestinations: single source of truth for the primary content
// destinations (Home / Platforms / Collections / Achievements / Search)
// and the route-path → active-tab derivation. Shared by `AppNav` (desktop
// top pill) and `BottomNav` (mobile bottom bar) so the two never drift in
// labels, icons, ordering, or active-state logic.
//
// Highlighting is derived from `route.path` (not route names) so gallery
// subroutes (e.g. `/rom/:id` reached from a platform) still light up
// their parent destination.
import { computed } from "vue";
import type { ComputedRef } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute } from "vue-router";

export type NavDestinationId =
  | "home"
  | "platforms"
  | "collections"
  | "achievements"
  | "search";

export interface NavDestination {
  id: NavDestinationId;
  label: string;
  // Mirrors `label`; RSegmentedControl sets it as each link's `aria-label`.
  ariaLabel: string;
  icon: string;
  to: string;
}

// Tab order and targets. useGamepad's LB/RB cycles through the same list.
export const NAV_TARGETS: readonly { id: NavDestinationId; to: string }[] = [
  { id: "home", to: "/" },
  { id: "platforms", to: "/platforms" },
  { id: "collections", to: "/collections" },
  { id: "achievements", to: "/achievements" },
  { id: "search", to: "/search" },
];

const NAV_META: Record<NavDestinationId, { labelKey: string; icon: string }> = {
  home: { labelKey: "common.home", icon: "mdi-home-outline" },
  platforms: { labelKey: "common.platforms", icon: "mdi-controller" },
  // Same glyph GameCard uses for its "add to collection" action:
  // keeps the icon stable across every generic "Collections" surface.
  collections: { labelKey: "common.collections", icon: "mdi-bookmark-outline" },
  achievements: { labelKey: "common.achievements", icon: "mdi-trophy-outline" },
  search: { labelKey: "common.search", icon: "mdi-magnify" },
};

/** Filled glyphs the bottom tab bar uses, as Apple's tab bar guidance prefers. */
export const NAV_FILLED_ICONS: Partial<Record<NavDestinationId, string>> = {
  home: "mdi-home",
  collections: "mdi-bookmark",
};

// `path` is `base` itself or a page under it, so "/platform-x" isn't.
function isUnder(path: string, base: string): boolean {
  return path === base || path.startsWith(`${base}/`);
}

/** The destination `path` belongs to; gallery sub-routes count as their parent. */
export function navDestinationAt(path: string): NavDestinationId | null {
  if (path === "/") return "home";
  if (isUnder(path, "/platforms") || isUnder(path, "/platform")) {
    return "platforms";
  }
  if (isUnder(path, "/collections") || isUnder(path, "/collection")) {
    return "collections";
  }
  if (isUnder(path, "/achievements")) return "achievements";
  if (isUnder(path, "/search")) return "search";
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
