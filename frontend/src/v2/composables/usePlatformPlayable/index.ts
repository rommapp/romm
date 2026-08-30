// usePlatformPlayable — reactive "can any ROM on this platform run
// in-browser?" check. Companion to useCanPlay (which takes a rom);
// platform-level surfaces (PlatformTile, PlatformListRow) only know the
// slug, so they read this instead. Reuses the same engine-support utils
// so the marker on the tile and the Play button on the ROM agree.
//
// `usePlatformPlayableChecker` is the batch sibling — returns a plain
// function (no per-call computed) for surfaces that need to test many
// slugs at once (sort comparators, group-by buckets in PlatformsIndex).
//
// `emulator` resolves to the in-browser engine that actually drives the
// platform: "ruffle" for Flash, "jsdos" for Windows 3.x/9x, "dosbox"
// when the EJS catalogue picks the dosbox_pure core (DOS is wrapped by
// EJS but distinctive enough to surface by name in the UI),
// "emulatorjs" for everything else playable, and `null` when nothing on
// the server can run it.
//
// `mode` folds the in-browser answer together with streaming: a platform
// served by a configured streaming container is playable too, just not in
// this tab. Streaming comes from the same `containerForPlatform` the Play
// button reads, so the badge can never disagree with the button.
import { storeToRefs } from "pinia";
import { computed, type ComputedRef } from "vue";
import i18n from "@/locales";
import storeConfig, { type Config } from "@/stores/config";
import storeHeartbeat, { type Heartbeat } from "@/stores/heartbeat";
import { useStreamingStore } from "@/stores/streaming";
import {
  getSupportedEJSCores,
  isEJSEmulationSupported,
  isJsDosEmulationSupported,
  isRuffleEmulationSupported,
  resolvePlatformSlug,
} from "@/utils";

export type PlatformEmulator =
  "emulatorjs" | "ruffle" | "jsdos" | "dosbox" | null;

export type PlatformPlayMode = "browser" | "stream" | "both" | null;

function resolveMode(playable: boolean, streamable: boolean): PlatformPlayMode {
  if (playable && streamable) return "both";
  if (playable) return "browser";
  if (streamable) return "stream";
  return null;
}

/** Pure helper — picks the engine that would actually run a platform.
 * Shared between the reactive and the batch composables so both surface
 * the same label for the same slug. */
function resolveEmulator(
  slug: string | null | undefined,
  heartbeat: Heartbeat,
  config: Config | undefined,
): PlatformEmulator {
  if (!slug) return null;
  if (isRuffleEmulationSupported(slug, heartbeat, config)) return "ruffle";
  if (isJsDosEmulationSupported(slug, heartbeat, config)) return "jsdos";
  if (!isEJSEmulationSupported(slug, heartbeat, config)) return null;
  const cores = getSupportedEJSCores(resolvePlatformSlug(slug, config));
  if (cores.includes("dosbox_pure")) return "dosbox";
  return "emulatorjs";
}

export function usePlatformPlayable(getSlug: () => string | null | undefined): {
  playable: ComputedRef<boolean>;
  emulator: ComputedRef<PlatformEmulator>;
  streamLabel: ComputedRef<string | null>;
  mode: ComputedRef<PlatformPlayMode>;
} {
  const heartbeatStore = storeHeartbeat();
  const configStore = storeConfig();
  const streamingStore = useStreamingStore();
  const { value: heartbeat } = storeToRefs(heartbeatStore);

  const emulator = computed<PlatformEmulator>(() =>
    resolveEmulator(getSlug(), heartbeat.value, configStore.config),
  );

  const playable = computed(() => emulator.value !== null);

  const streamContainer = computed(() =>
    streamingStore.containerForPlatform(getSlug()),
  );

  const streamable = computed(() => streamContainer.value !== null);

  // The container's label is what the Play button says, so the tooltip says
  // the same. Unlabelled containers fall back to the emulator, which the
  // backend always fills in.
  const streamLabel = computed(() => {
    const container = streamContainer.value;
    if (!container) return null;
    return container.label || container.emulator || null;
  });

  const mode = computed<PlatformPlayMode>(() =>
    resolveMode(playable.value, streamable.value),
  );

  return { playable, emulator, streamLabel, mode };
}

export function usePlatformPlayableChecker(): {
  isPlayable: ComputedRef<(slug: string | null | undefined) => boolean>;
  getEmulator: ComputedRef<
    (slug: string | null | undefined) => PlatformEmulator
  >;
  isStreamable: ComputedRef<(slug: string | null | undefined) => boolean>;
} {
  const heartbeatStore = storeHeartbeat();
  const configStore = storeConfig();
  const streamingStore = useStreamingStore();
  const { value: heartbeat } = storeToRefs(heartbeatStore);

  // Expose computed functions so callers that consume them inside another
  // computed (sort comparator, bucket discriminator) re-run when the
  // heartbeat or admin-toggle state changes.
  const getEmulator = computed(() => {
    const hb = heartbeat.value;
    const cfg = configStore.config;
    return (slug: string | null | undefined): PlatformEmulator =>
      resolveEmulator(slug, hb, cfg);
  });

  const isPlayable = computed(() => {
    const resolve = getEmulator.value;
    return (slug: string | null | undefined) => resolve(slug) !== null;
  });

  const isStreamable = computed(() => {
    // Read the config object so the returned function is rebuilt when
    // /config lands or an admin changes it.
    const cfg = streamingStore.config;
    return (slug: string | null | undefined): boolean =>
      cfg.enabled && streamingStore.containerForPlatform(slug) !== null;
  });

  return { isPlayable, getEmulator, isStreamable };
}

/** Human-readable tooltip for the play badge / column. Shared by every
 * surface so the wording stays in lock-step. */
export function playTooltip(
  mode: PlatformPlayMode,
  emulator: PlatformEmulator,
  streamLabel: string | null,
): string {
  const t = i18n.global.t;
  switch (mode) {
    case "both":
      return t("platform.playable-both", { label: streamLabel ?? "" });
    case "stream":
      return t("platform.playable-stream", { label: streamLabel ?? "" });
    case "browser":
      switch (emulator) {
        case "ruffle":
          return t("platform.playable-browser-ruffle");
        case "jsdos":
          return t("platform.playable-browser-jsdos");
        case "dosbox":
          return t("platform.playable-browser-dosbox");
        default:
          return t("platform.playable-browser-emulatorjs");
      }
    case null:
      return t("platform.playable-none");
  }
}
