// useGalleryProvenance: did the user reach the details view by clicking
// through from a gallery?
//
// The gallery store keeps `romIdIndex` (and its loaded windows) alive
// after the user leaves the gallery, so going back restores it instantly.
// Membership in that list is therefore not evidence that the user is
// still browsing it: opening a ROM from Home, Activity or a scan result
// would otherwise inherit the previous gallery's neighbours and offer to
// step through a list the user has left. This guard records how the
// current details chain was entered, so PrevNextNav can tell a real
// gallery walk from a stale index.
//
// Only arrivals at the details view update the flag. Hops that stay
// inside the chain (rom to rom via the arrows or a related game, and the
// round trip through a player) leave it untouched, so the arrows survive
// a play session.
import { computed, ref } from "vue";
import type { Router } from "vue-router";
import { ROUTES } from "@/plugins/router";

const GALLERY_ROUTES: ReadonlySet<string> = new Set([
  ROUTES.PLATFORM,
  ROUTES.COLLECTION,
  ROUTES.VIRTUAL_COLLECTION,
  ROUTES.SMART_COLLECTION,
  ROUTES.SEARCH,
]);

const CHAIN_ROUTES: ReadonlySet<string> = new Set([
  ROUTES.ROM,
  ROUTES.EMULATORJS,
  ROUTES.RUFFLE,
  ROUTES.STREAM,
]);

const enteredFromGallery = ref(false);

/** Register the tracker on the app router. Returns the remove function. */
export function installGalleryProvenance(router: Router): () => void {
  return router.afterEach((to, from) => {
    if (to.name !== ROUTES.ROM) return;
    const fromName = String(from.name ?? "");
    if (CHAIN_ROUTES.has(fromName)) return;
    enteredFromGallery.value = GALLERY_ROUTES.has(fromName);
  });
}

export function useGalleryProvenance() {
  return {
    enteredFromGallery: computed(() => enteredFromGallery.value),
  };
}
