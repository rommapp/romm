// usePlatformPlayable — reactive "can any ROM on this platform run
// in-browser?" check. Companion to useCanPlay (which takes a rom);
// platform-level surfaces (PlatformTile, PlatformListRow) only know the
// slug, so they read this instead. Reuses the same EJS + Ruffle utils
// so the marker on the tile and the Play button on the ROM agree.
import { storeToRefs } from "pinia";
import { computed, type ComputedRef } from "vue";
import storeConfig from "@/stores/config";
import storeHeartbeat from "@/stores/heartbeat";
import { isEJSEmulationSupported, isRuffleEmulationSupported } from "@/utils";

export function usePlatformPlayable(getSlug: () => string | null | undefined): {
  playable: ComputedRef<boolean>;
  playableEJS: ComputedRef<boolean>;
  playableRuffle: ComputedRef<boolean>;
} {
  const heartbeatStore = storeHeartbeat();
  const configStore = storeConfig();
  const { value: heartbeat } = storeToRefs(heartbeatStore);

  const playableEJS = computed(() => {
    const slug = getSlug();
    if (!slug) return false;
    return isEJSEmulationSupported(slug, heartbeat.value, configStore.config);
  });

  const playableRuffle = computed(() => {
    const slug = getSlug();
    if (!slug) return false;
    return isRuffleEmulationSupported(
      slug,
      heartbeat.value,
      configStore.config,
    );
  });

  const playable = computed(() => playableEJS.value || playableRuffle.value);

  return { playable, playableEJS, playableRuffle };
}
