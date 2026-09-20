// useWebpSupport — single-source resolution of whether the backend serves
// .webp covers for this server. The WebP conversion task is what writes the
// `.webp` sibling next to every cover, so its heartbeat flag is the signal.
//
// Use this everywhere a feature needs to decide whether to rewrite cover
// URLs `.png|.jpg|.jpeg` → `.webp`.
//
//   const { supportsWebp, toWebp } = useWebpSupport();
//   <img :src="toWebp(rom.path_cover_large)" />
//
// Code without a component instance (a pure resolver, a store) reaches for
// `toWebpUrl` and passes the flag in.
import { storeToRefs } from "pinia";
import { computed, type ComputedRef } from "vue";
import storeHeartbeat from "@/stores/heartbeat";

// The extension ends the *path*, not the URL: a cover arrives from the backend
// as `.../cover/big.png?ts=<updated_at>`, so anchoring on the end of the string
// would never match one.
const RASTER_EXT = /\.(png|jpe?g)(?=$|[?#])/i;

/** Point a cover URL at its converted sibling, when the server serves them. */
export function toWebpUrl(url: string, supportsWebp: boolean): string {
  return supportsWebp ? url.replace(RASTER_EXT, ".webp") : url;
}

export function useWebpSupport(): {
  supportsWebp: ComputedRef<boolean>;
  toWebp: (url: string | null | undefined) => string;
} {
  const heartbeatStore = storeHeartbeat();
  const { value } = storeToRefs(heartbeatStore);

  const supportsWebp = computed<boolean>(() =>
    Boolean(value.value.TASKS?.ENABLE_SCHEDULED_CONVERT_IMAGES_TO_WEBP),
  );

  function toWebp(url: string | null | undefined): string {
    if (!url) return "";
    return toWebpUrl(url, supportsWebp.value);
  }

  return { supportsWebp, toWebp };
}
