// useWebpSupport — single-source resolution of whether the backend serves
// .webp covers for this server. The flag is exposed as
// `FRONTEND.IMAGES_WEBP` on the heartbeat response, but `FrontendDict` in
// the generated OpenAPI types currently omits it (backend debt — when the
// schema is updated and regenerated, the cast below disappears and the
// composable becomes a thin wrapper).
//
// Use this everywhere a feature needs to decide whether to rewrite cover
// URLs `.png|.jpg|.jpeg` → `.webp`.
//
//   const { supportsWebp, toWebp } = useWebpSupport();
//   <img :src="toWebp(rom.path_cover_large)" />
import { storeToRefs } from "pinia";
import { computed, type ComputedRef } from "vue";
import storeHeartbeat from "@/stores/heartbeat";

interface FrontendWithWebp {
  FRONTEND?: { IMAGES_WEBP?: boolean };
}

const RASTER_EXT = /\.(png|jpe?g)$/i;

export function useWebpSupport(): {
  supportsWebp: ComputedRef<boolean>;
  toWebp: (url: string | null | undefined) => string;
} {
  const heartbeatStore = storeHeartbeat();
  const { value } = storeToRefs(heartbeatStore);

  const supportsWebp = computed<boolean>(() =>
    Boolean(
      (value.value as unknown as FrontendWithWebp)?.FRONTEND?.IMAGES_WEBP,
    ),
  );

  function toWebp(url: string | null | undefined): string {
    if (!url) return "";
    return supportsWebp.value ? url.replace(RASTER_EXT, ".webp") : url;
  }

  return { supportsWebp, toWebp };
}
