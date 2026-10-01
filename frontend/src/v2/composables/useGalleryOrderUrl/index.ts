// useGalleryOrderUrl - bookmarkable gallery sort via URL query params.
//
//   ?orderBy=fs_size_bytes  (omitted at the view's default, "name" unless set)
//   ?orderDir=desc          (omitted at "asc",  the default)
//
// A `null` default (Search) leaves the order to the backend, which ranks
// by relevance until the user picks a column.
//
// An unrecognised or absent param resolves to the default, so a link
// without them lands on the same sort whatever the last gallery left in
// the store. Hydration runs during setup, before the shell registers its
// refetch watch, so the first fetch carries the params without echoing.
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

function parseOrderBy(
  value: unknown,
  fallback: GalleryOrderKey | null,
): GalleryOrderKey | null {
  return typeof value === "string" && isGalleryOrderKey(value)
    ? value
    : fallback;
}

function parseOrderDir(value: unknown): GalleryOrderDir {
  return typeof value === "string" && isGalleryOrderDir(value)
    ? value
    : DEFAULT_ORDER_DIR;
}

export function useGalleryOrderUrl(
  defaultOrderBy: GalleryOrderKey | null = DEFAULT_ORDER_BY,
) {
  const route = useRoute();
  const router = useRouter();
  const galleryRoms = storeGalleryRoms();
  const { orderBy, orderDir } = storeToRefs(galleryRoms);

  function applyFromUrl() {
    const by = parseOrderBy(route.query.orderBy, defaultOrderBy);
    const dir = parseOrderDir(route.query.orderDir);
    if (by !== orderBy.value) galleryRoms.setOrderBy(by);
    if (dir !== orderDir.value) galleryRoms.setOrderDir(dir);
  }

  applyFromUrl();

  watch(() => [route.query.orderBy, route.query.orderDir], applyFromUrl);

  // Drop the param when the value is the default, which keeps URLs clean.
  watch([orderBy, orderDir], ([by, dir]) => {
    syncQueryParam(
      router,
      "orderBy",
      by === defaultOrderBy || by === null ? undefined : by,
    );
    syncQueryParam(
      router,
      "orderDir",
      dir === DEFAULT_ORDER_DIR ? undefined : dir,
    );
  });
}
