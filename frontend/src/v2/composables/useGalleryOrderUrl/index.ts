// useGalleryOrderUrl — bookmarkable gallery sort via URL query params.
// Round-trips `galleryRoms.orderBy` / `orderDir` (written by the list
// column headers and the toolbar direction toggle) through the route.
//
// Why: per constitution §VI.D, active filters / search query / sort are
// bookmarkable session state. The URL holds them so a copied link
// reproduces the sender's view.
//
// Parameter encoding:
//   * ?orderBy=fs_size_bytes  (omitted when "name", the default)
//   * ?orderDir=desc          (omitted when "asc",  the default)
//
// Direction notes mirror useGalleryViewModeUrl:
//   * URL → store fires on every route.query.{orderBy,orderDir} change
//     (back/forward, pasted URLs, programmatic navigation). An absent or
//     unrecognised param resolves to the default, so a link without the
//     params always lands on the same sort regardless of what the
//     previous gallery left in the store.
//   * Store → URL pushes via `syncQueryParam`, whose comparison guard
//     prevents a feedback loop with the URL → store watcher.
//   * The URL is applied during setup, before the shell's refetch watch is
//     registered and before the view's first fetch, so the bootstrap
//     request already carries the right order params without echoing.
import { storeToRefs } from "pinia";
import { watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import storeGalleryRoms, {
  DEFAULT_ORDER_BY,
  DEFAULT_ORDER_DIR,
  type GalleryOrderDir,
  type GalleryOrderKey,
  isGalleryOrderDir,
  isGalleryOrderKey,
} from "@/v2/stores/galleryRoms";
import { syncQueryParam } from "@/v2/utils/routeQuery";

function parseOrderBy(value: unknown): GalleryOrderKey {
  return typeof value === "string" && isGalleryOrderKey(value)
    ? value
    : DEFAULT_ORDER_BY;
}

function parseOrderDir(value: unknown): GalleryOrderDir {
  return typeof value === "string" && isGalleryOrderDir(value)
    ? value
    : DEFAULT_ORDER_DIR;
}

export function useGalleryOrderUrl() {
  const route = useRoute();
  const router = useRouter();
  const galleryRoms = storeGalleryRoms();
  const { orderBy, orderDir } = storeToRefs(galleryRoms);

  function applyFromUrl() {
    const by = parseOrderBy(route.query.orderBy);
    const dir = parseOrderDir(route.query.orderDir);
    if (by !== orderBy.value) galleryRoms.setOrderBy(by);
    if (dir !== orderDir.value) galleryRoms.setOrderDir(dir);
  }

  applyFromUrl();

  watch(() => route.query.orderBy, applyFromUrl);
  watch(() => route.query.orderDir, applyFromUrl);

  // Drop the param when the value is the default, which keeps URLs clean.
  watch(orderBy, (next) => {
    syncQueryParam(
      router,
      "orderBy",
      next === DEFAULT_ORDER_BY ? undefined : next,
    );
  });
  watch(orderDir, (next) => {
    syncQueryParam(
      router,
      "orderDir",
      next === DEFAULT_ORDER_DIR ? undefined : next,
    );
  });
}
