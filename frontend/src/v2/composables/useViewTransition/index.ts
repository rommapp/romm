// useViewTransition — tiny wrapper around the browser View Transitions API
// for shared-element morphs (e.g. game card cover → GameDetails cover).
//
// Usage at the source side (the element you click):
//
//   const { morphTransition } = useViewTransition();
//   function onClick(e: MouseEvent) {
//     e.preventDefault();
//     if (!coverEl.value) return router.push(href);
//     morphTransition(
//       { el: coverEl.value, name: `rom-cover-${rom.id}` },
//       () => router.push(href),
//     );
//   }
//
// At the destination side, just paint a static `view-transition-name` on
// the matching element — the browser pairs it with the source by name.
// One element per name on screen at a time; we tag the source imperatively
// so two visible cards with the same ROM never collide.
//
// Graceful degradation:
//   * `prefers-reduced-motion: reduce` → no transition, just navigate.
//   * Browser without `document.startViewTransition` → just navigate.
import { nextTick, ref } from "vue";
import type { RouteLocationNormalized, Router } from "vue-router";

export interface MorphSource {
  el: HTMLElement;
  name: string;
}

// Module-level singleton — when set, source-side tiles in the destination
// view (GameCard, CollectionTile, PlatformTile, GameList row) reactively
// paint `view-transition-name: <pending>` on their visual element so the
// browser can morph from the previous view's hero/cover/icon back into
// the matching tile. Cleared after `transition.finished`. Format examples:
//   "rom-cover-{id}"
//   "platform-icon-{id}"
//   "coll-cover-{regular|virtual|smart}-{id}"
export const pendingMorphName = ref<string | null>(null);

// True while `morphTransition` (forward direction) is running its own
// `document.startViewTransition`. The back-morph guard reads this and
// skips so a click-driven forward morph doesn't get cancelled by a nested
// transition starting from `beforeResolve`.
let forwardTransitionActive = false;

function isSupported(): boolean {
  return (
    typeof document !== "undefined" &&
    typeof document.startViewTransition === "function"
  );
}

function prefersReducedMotion(): boolean {
  return (
    typeof window !== "undefined" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches
  );
}

export function useViewTransition() {
  function morphTransition(
    source: MorphSource,
    navigate: () => void | Promise<void>,
  ): void {
    if (!isSupported() || prefersReducedMotion()) {
      void navigate();
      return;
    }

    // Tag the source element so the browser captures it as a separate
    // transition layer. The destination element carries the same name in
    // its template, so the snapshots get paired automatically.
    source.el.style.viewTransitionName = source.name;

    forwardTransitionActive = true;
    const transition = document.startViewTransition(async () => {
      await navigate();
    });

    // Clean up the inline style after the transition finishes — the
    // source element usually unmounts during navigate(), but if a route
    // keeps it alive (kept-alive view, error mid-nav, …) we don't want a
    // dangling view-transition-name on the page.
    transition.finished.finally(() => {
      forwardTransitionActive = false;
      if (source.el.isConnected) {
        source.el.style.viewTransitionName = "";
      }
    });
  }

  return { morphTransition, isSupported };
}

// Map a route to the morph tag of the visual element it owns. When the
// user leaves this route, the destination view paints the same tag on
// the matching tile so the browser can pair the snapshots.
function morphNameForRoute(route: RouteLocationNormalized): string | null {
  const name = route.name;
  const params = route.params as Record<string, string | string[]>;
  if (name === "rom" && params.rom) return `rom-cover-${params.rom}`;
  if (name === "platform" && params.platform) {
    return `platform-icon-${params.platform}`;
  }
  if (name === "collection" && params.collection) {
    return `coll-cover-regular-${params.collection}`;
  }
  if (name === "virtual-collection" && params.collection) {
    return `coll-cover-virtual-${params.collection}`;
  }
  if (name === "smart-collection" && params.collection) {
    return `coll-cover-smart-${params.collection}`;
  }
  return null;
}

// Install a router guard that morphs the leaving view's hero element
// back into the matching tile in the destination view — covers BackBtn,
// navbar clicks, and the browser back button (all flow through the same
// Vue Router pipeline). Source-route mapping lives in `morphNameForRoute`
// so the guard stays generic across rom/platform/collection.
//
// Choreography:
//   1. beforeResolve fires while we're still on the source route.
//   2. We compute the morph tag and store it in pendingMorphName so the
//      destination tile (GameCard / PlatformTile / CollectionTile / list
//      row) paints `view-transition-name: <tag>` reactively on render.
//   3. We start the transition; inside the callback we resolve the guard
//      so the router commits, then await two ticks for Vue to flush the
//      destination view's DOM.
//   4. Browser snapshots NEW, morphs between them.
//   5. transition.finished clears pendingMorphName.
//
// Skips when a forward `morphTransition` is already running so the two
// don't fight over `document.startViewTransition`.
export function installBackMorph(router: Router): () => void {
  const removeGuard = router.beforeResolve(async (to, from) => {
    if (forwardTransitionActive) return true;
    if (!isSupported() || prefersReducedMotion()) return true;
    // No morph between two views of the same kind (e.g. /platform/A →
    // /platform/B) — that would compete with the in-route transition
    // and there's no shared element to pair anyway.
    if (from.name && to.name === from.name) return true;

    const tag = morphNameForRoute(from);
    if (!tag) return true;

    pendingMorphName.value = tag;

    await new Promise<void>((resolveGuard) => {
      const transition = document.startViewTransition(async () => {
        // Let the route advance; once the router commits, Vue re-renders
        // the destination view, and the matching tile now carries the
        // view-transition-name.
        resolveGuard();
        await nextTick();
        await nextTick();
      });
      transition.finished.finally(() => {
        pendingMorphName.value = null;
      });
    });

    return true;
  });
  return removeGuard;
}
