// useCanPlay: reactive "can this ROM be played in the browser?" check.
// v1 duplicated this logic across GameCard, GameDetails and the play menu
// inside PlayBtn.vue; v2 lifts it to a composable so the card overlay
// and the menu item agree with the details-header CTA.
//
// "Playable" means EJS, js-dos, PICO-8, EasyRPG, or Ruffle can run the platform on this
// server (admin toggles + platform support + WebGL availability) and there
// is a file to boot, or a streaming container is configured for the
// platform, or the desktop shell has a locally installed emulator for it.
// A physical game or one missing from the filesystem has nothing
// to hand the emulator, js-dos additionally needs the file to be one of its
// own bundles, and EasyRPG an extracted game folder. The individual flags are
// exposed so the play action can pick the right route (EJS vs js-dos vs
// PICO-8 vs EasyRPG vs Ruffle vs Stream vs Native).
import { storeToRefs } from "pinia";
import { computed, type ComputedRef } from "vue";
import storeConfig from "@/stores/config";
import storeHeartbeat from "@/stores/heartbeat";
import { useNativeStore } from "@/stores/native";
import type { SimpleRom } from "@/stores/roms";
import { useStreamingStore } from "@/stores/streaming";
import {
  isEasyRpgEmulationSupported,
  isEasyRpgGame,
  isEJSEmulationSupported,
  isJsDosBundle,
  isJsDosEmulationSupported,
  isPico8EmulationSupported,
  isPico8Rom,
  isRuffleEmulationSupported,
} from "@/utils";
import { useCan } from "@/v2/composables/useCan";

export function useCanPlay(getRom: () => SimpleRom | null | undefined): {
  canPlay: ComputedRef<boolean>;
  canPlayEJS: ComputedRef<boolean>;
  canPlayJsDos: ComputedRef<boolean>;
  canPlayPico8: ComputedRef<boolean>;
  canPlayEasyRpg: ComputedRef<boolean>;
  canPlayRuffle: ComputedRef<boolean>;
  canReachStream: ComputedRef<boolean>;
  canPlayStream: ComputedRef<boolean>;
  canPlayNative: ComputedRef<boolean>;
} {
  const heartbeatStore = storeHeartbeat();
  const configStore = storeConfig();
  const streamingStore = useStreamingStore();
  const nativeStore = useNativeStore();
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

  const onPico8Platform = supportedBy(isPico8EmulationSupported);
  const canPlayPico8 = computed(
    () => onPico8Platform.value && isPico8Rom(getRom()),
  );

  const onEasyRpgPlatform = supportedBy(isEasyRpgEmulationSupported);
  const canPlayEasyRpg = computed(
    () => onEasyRpgPlatform.value && isEasyRpgGame(getRom()),
  );

  // The broker is handed the ROM file, so a physical game or one missing
  // from the filesystem has nothing to stream any more than it has to boot.
  // Reaching the stream is enough to join one; starting one takes a grant.
  const canReachStream = computed(() => {
    const rom = getRom();
    if (!rom?.has_file_on_disk) return false;
    return streamingStore.containerForPlatform(rom.platform_slug) !== null;
  });
  const canStartStream = useCan("stream.start");
  const canPlayStream = computed(
    () => canReachStream.value && canStartStream.value,
  );

  // The shell either downloads the file or reads it off disk, so the same
  // "something to boot" rule applies.
  const canPlayNative = computed(() => {
    const rom = getRom();
    if (!rom?.has_file_on_disk) return false;
    return nativeStore.isSupportedPlatform(rom.platform_slug);
  });

  const canPlay = computed(
    () =>
      canPlayEJS.value ||
      canPlayJsDos.value ||
      canPlayPico8.value ||
      canPlayEasyRpg.value ||
      canPlayRuffle.value ||
      canPlayStream.value ||
      canPlayNative.value,
  );

  return {
    canPlay,
    canPlayEJS,
    canPlayJsDos,
    canPlayPico8,
    canPlayEasyRpg,
    canPlayRuffle,
    canReachStream,
    canPlayStream,
    canPlayNative,
  };
}
