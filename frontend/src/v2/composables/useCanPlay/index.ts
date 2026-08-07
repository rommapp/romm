// useCanPlay — reactive "is this ROM playable in-browser?" check, shared
// by every surface that renders the Play action (GameCard overlay,
// GameActions ribbon, GameActionsList more-menu). v1 had the same gate
// inside PlayBtn.vue; v2 lifts it to a composable so the card overlay
// and the menu item agree with the details-header CTA.
//
// "Playable" means EJS or Ruffle can run the platform on this server
// (admin toggles + platform support + WebGL availability), or a
// streaming container is configured for the platform. Individual flags
// are exposed so the play action can pick the right route (EJS vs
// Ruffle vs Stream).
import { storeToRefs } from "pinia";
import { computed, type ComputedRef } from "vue";
import storeConfig from "@/stores/config";
import storeHeartbeat from "@/stores/heartbeat";
import type { SimpleRom } from "@/stores/roms";
import { useStreamingStore } from "@/stores/streaming";
import { isEJSEmulationSupported, isRuffleEmulationSupported } from "@/utils";

export function useCanPlay(getRom: () => SimpleRom | null | undefined): {
  canPlay: ComputedRef<boolean>;
  canPlayEJS: ComputedRef<boolean>;
  canPlayRuffle: ComputedRef<boolean>;
  canPlayStream: ComputedRef<boolean>;
} {
  const heartbeatStore = storeHeartbeat();
  const configStore = storeConfig();
  const streamingStore = useStreamingStore();
  const { value: heartbeat } = storeToRefs(heartbeatStore);

  const canPlayEJS = computed(() => {
    const rom = getRom();
    if (!rom) return false;
    return isEJSEmulationSupported(
      rom.platform_slug,
      heartbeat.value,
      configStore.config,
    );
  });

  const canPlayRuffle = computed(() => {
    const rom = getRom();
    if (!rom) return false;
    return isRuffleEmulationSupported(
      rom.platform_slug,
      heartbeat.value,
      configStore.config,
    );
  });

  const canPlayStream = computed(() => {
    const rom = getRom();
    if (!rom) return false;
    return streamingStore.containerForPlatform(rom.platform_slug) !== null;
  });

  const canPlay = computed(
    () => canPlayEJS.value || canPlayRuffle.value || canPlayStream.value,
  );

  return { canPlay, canPlayEJS, canPlayRuffle, canPlayStream };
}
