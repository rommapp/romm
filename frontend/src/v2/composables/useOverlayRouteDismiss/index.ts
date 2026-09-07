// useOverlayRouteDismiss: a route change takes the open overlays with it.
//
// v2 dialogs are mounted once by GlobalDialogs at the layout level, above
// the <router-view>, so nothing tears them down when the route changes.
// Browser back / forward (and any navigation triggered from inside a
// dialog) swapped the page underneath the panel and left it floating over
// a view it has nothing to do with. Every escapable v2 surface already
// registers itself while open, so the shared escape stack is the
// dismissal list.
//
// Only a change of route identity dismisses. Gallery filters, view mode,
// tile search and the details subtabs all `router.replace` their state
// into the query string while an overlay is open (useGalleryFilterUrl,
// FilterDrawer, ...), and those updates must leave it alone.
import { nextTick } from "vue";
import type { Router } from "vue-router";
import {
  closeAllEscapables,
  hasOpenEscapable,
} from "@/v2/lib/overlays/RDialog/escapeStack";

/** Register the guard on the app router. Returns the remove function. */
export function installOverlayRouteDismiss(router: Router): () => void {
  return router.beforeEach(async (to, from) => {
    if (to.path === from.path) return;
    if (!hasOpenEscapable()) return;
    closeAllEscapables();
    // Let the overlays leave the DOM before the navigation resolves, so
    // the back-morph view transition (installBackMorph, a beforeResolve
    // guard) snapshots the page without a panel on top of it.
    await nextTick();
  });
}
