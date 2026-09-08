// useCanPlay — reactive "can this ROM be played in the browser?" check.
// v1 duplicated this logic across GameCard, GameDetails and the play menu
// inside PlayBtn.vue; v2 lifts it to a composable so the card overlay
// and the menu item agree with the details-header CTA.
//
// "Playable" means EJS, js-dos, or Ruffle can run the platform on this
// server (admin toggles + platform support + WebGL availability) and there
// is a file to boot, or a streaming container is configured for the
// platform. A physical game or one missing from the filesystem has nothing
// to hand the emulator, and js-dos additionally needs the file to be one of
// its own bundles. The individual flags are exposed so the play action can
// pick the right route (EJS vs js-dos vs Ruffle vs Stream).
import { storeToRefs } from "pinia";
import { computed, type ComputedRef } from "vue";
import storeConfig from "@/stores/config";
import storeHeartbeat from "@/stores/heartbeat";
import type { SimpleRom } from "@/stores/roms";
import { useStreamingStore } from "@/stores/streaming";
import {
  isEJSEmulationSupported,
  isJsDosBundle,
  isJsDosEmulationSupported,
  isRuffleEmulationSupported,
} from "@/utils";

export function useCanPlay(getRom: () => SimpleRom | null | undefined): {
  canPlay: ComputedRef<boolean>;
  canPlayEJS: ComputedRef<boolean>;
  canPlayJsDos: ComputedRef<boolean>;
  canPlayRuffle: ComputedRef<boolean>;
  canPlayStream: ComputedRef<boolean>;
} {
  const heartbeatStore = storeHeartbeat();
  const configStore = storeConfig();
  const streamingStore = useStreamingStore();
  const { value: heartbeat } = storeToRefs(heartbeatStore);

  const supportedBy = (check: typeof isEJSEmulationSupported) =>
    computed(() => {
      const rom = getRom();
      if (!rom?.has_file_on_disk) return false;
      return check(rom.platform_slug, heartbeat.value, configStore.config);
    });

  const canPlayEJS = supportedBy(isEJSEmulationSupported);
  const canPlayRuffle = supportedBy(isRuffleEmulationSupported);

  // js-dos boots only its own `.jsdos` bundle, so the platform alone would
  // offer Play on files the player panics on.
  const onJsDosPlatform = supportedBy(isJsDosEmulationSupported);
  const canPlayJsDos = computed(
    () => onJsDosPlatform.value && isJsDosBundle(getRom()),
  );

  // The broker is handed the ROM file, so a physical game or one missing
  // from the filesystem has nothing to stream any more than it has to boot.
  const canPlayStream = computed(() => {
    const rom = getRom();
    if (!rom?.has_file_on_disk) return false;
    return streamingStore.containerForPlatform(rom.platform_slug) !== null;
  });

  const canPlay = computed(
    () =>
      canPlayEJS.value ||
      canPlayJsDos.value ||
      canPlayRuffle.value ||
      canPlayStream.value,
  );

  return { canPlay, canPlayEJS, canPlayJsDos, canPlayRuffle, canPlayStream };
}
