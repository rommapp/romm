// useWebpSupport — single-source resolution of whether the backend serves
// .webp covers for this server. The WebP conversion task is what writes the
// `.webp` sibling next to every cover, so its heartbeat flag is the signal.
//
// Use this everywhere a feature needs to decide whether to rewrite cover
// URLs `.png|.jpg|.jpeg` → `.webp`.
//
//   const { supportsWebp, toWebp } = useWebpSupport();
//   <img :src="toWebp(rom.path_cover_large)" />
import { storeToRefs } from "pinia";
import { computed, type ComputedRef } from "vue";
import storeHeartbeat from "@/stores/heartbeat";

const RASTER_EXT = /\.(png|jpe?g)$/i;

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
    return supportsWebp.value ? url.replace(RASTER_EXT, ".webp") : url;
  }

  return { supportsWebp, toWebp };
}
