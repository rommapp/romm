// usePlatformPlayable — reactive "can any ROM on this platform run
// in-browser?" check. Companion to useCanPlay (which takes a rom);
// platform-level surfaces (PlatformTile, PlatformListRow) only know the
// slug, so they read this instead. Reuses the same EJS + Ruffle utils
// so the marker on the tile and the Play button on the ROM agree.
//
// `usePlatformPlayableChecker` is the batch sibling — returns a plain
// function (no per-call computed) for surfaces that need to test many
// slugs at once (sort comparators, group-by buckets in PlatformsIndex).
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

export function usePlatformPlayableChecker(): {
  isPlayable: ComputedRef<(slug: string | null | undefined) => boolean>;
} {
  const heartbeatStore = storeHeartbeat();
  const configStore = storeConfig();
  const { value: heartbeat } = storeToRefs(heartbeatStore);

  // Expose a computed function so callers that consume it inside another
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

  return { isPlayable };
}
