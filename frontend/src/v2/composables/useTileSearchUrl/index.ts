// useTileSearchUrl — bookmarkable per-view tile search backed by the
// route's `?search=` query param.
//
// Used by index views (Platforms, Collections) to filter their tile
// lists by name. The local-state cousin of `useGalleryFilterUrl`, which
// sits on top of the v1 galleryFilter Pinia store and is consumed by
// `GalleryShell`. Tile indexes don't drive a server-side fetch so a
// shared store would be overkill — a local ref is enough.
//
// Why: per constitution §VI.D, active filters / search query are
// bookmarkable session state. The URL holds the value so a copied link
// reproduces what the sender sees.
//
// Direction notes:
//   * URL → ref fires on every route.query.search change (back/forward,
//     pasted URLs).
//   * Ref → URL pushes via `router.replace` (no history entry per
//     keystroke). Skips the push when the URL already matches.
import { ref, watch, type Ref } from "vue";
import { useRoute, useRouter } from "vue-router";

export function useTileSearchUrl(): Ref<string> {
  const route = useRoute();
  const router = useRouter();

  const initial =
    typeof route.query.search === "string" ? route.query.search : "";
  const term = ref<string>(initial);

  watch(
    () => route.query.search,
    (q) => {
      const v = typeof q === "string" ? q : "";
      if (v !== term.value) term.value = v;
    },
  );

  watch(term, (next) => {
    const desired = next && next.length > 0 ? next : undefined;
    const current =
      typeof route.query.search === "string" ? route.query.search : undefined;
    if (desired === current) return;
    const nextQuery = { ...route.query };
    if (desired === undefined) delete nextQuery.search;
    else nextQuery.search = desired;
    router.replace({ query: nextQuery });
  });

  return term;
}
