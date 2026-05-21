// usePlatformPlayable — reactive "can any ROM on this platform run
// in-browser?" check. Companion to useCanPlay (which takes a rom);
// platform-level surfaces (PlatformTile, PlatformListRow) only know the
// slug, so they read this instead. Reuses the same EJS + Ruffle utils
// so the marker on the tile and the Play button on the ROM agree.
//
// `usePlatformPlayableChecker` is the batch sibling — returns a plain
// function (no per-call computed) for surfaces that need to test many
// slugs at once (sort comparators, group-by buckets in PlatformsIndex).
//
// `emulator` resolves to the in-browser engine that actually drives the
// platform: "ruffle" for Flash, "dosbox" when the EJS catalogue picks
// the dosbox_pure core (DOS is wrapped by EJS but distinctive enough to
// surface by name in the UI), "emulatorjs" for everything else playable,
// and `null` when nothing on the server can run it.
import { storeToRefs } from "pinia";
import { computed, type ComputedRef } from "vue";
import storeConfig, { type Config } from "@/stores/config";
import storeHeartbeat, { type Heartbeat } from "@/stores/heartbeat";
import {
  getSupportedEJSCores,
  isEJSEmulationSupported,
  isRuffleEmulationSupported,
} from "@/utils";

export type PlatformEmulator = "emulatorjs" | "ruffle" | "dosbox" | null;

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
  if (!isEJSEmulationSupported(slug, heartbeat, config)) return null;
  const resolved = config?.PLATFORMS_VERSIONS[slug] || slug;
  const cores = getSupportedEJSCores(resolved);
  if (cores.includes("dosbox_pure")) return "dosbox";
  return "emulatorjs";
}

export function usePlatformPlayable(getSlug: () => string | null | undefined): {
  playable: ComputedRef<boolean>;
  playableEJS: ComputedRef<boolean>;
  playableRuffle: ComputedRef<boolean>;
  emulator: ComputedRef<PlatformEmulator>;
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

  const emulator = computed<PlatformEmulator>(() =>
    resolveEmulator(getSlug(), heartbeat.value, configStore.config),
  );

  return { playable, playableEJS, playableRuffle, emulator };
}

export function usePlatformPlayableChecker(): {
  isPlayable: ComputedRef<(slug: string | null | undefined) => boolean>;
  getEmulator: ComputedRef<
    (slug: string | null | undefined) => PlatformEmulator
  >;
} {
  const heartbeatStore = storeHeartbeat();
  const configStore = storeConfig();
  const { value: heartbeat } = storeToRefs(heartbeatStore);

  // Expose computed functions so callers that consume them inside another
  // computed (sort comparator, bucket discriminator) re-run when the
  // heartbeat or admin-toggle state changes.
  const isPlayable = computed(() => {
    const hb = heartbeat.value;
    const cfg = configStore.config;
    return (slug: string | null | undefined) => {
      if (!slug) return false;
      return (
        isEJSEmulationSupported(slug, hb, cfg) ||
        isRuffleEmulationSupported(slug, hb, cfg)
      );
    };
  });

  const getEmulator = computed(() => {
    const hb = heartbeat.value;
    const cfg = configStore.config;
    return (slug: string | null | undefined): PlatformEmulator =>
      resolveEmulator(slug, hb, cfg);
  });

  return { isPlayable, getEmulator };
}

/** Human-readable tooltip for the playable badge / column. Shared by
 * every surface so the wording stays in lock-step. */
export function playableTooltip(emulator: PlatformEmulator): string {
  switch (emulator) {
    case "ruffle":
      return "Playable in browser through Ruffle";
    case "dosbox":
      return "Playable in browser through DOSBox";
    case "emulatorjs":
      return "Playable in browser through EmulatorJS";
    case null:
      return "Not supported by EmulatorJS";
  }
}
