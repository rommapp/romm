// useBackgroundArt
//
// The AppLayout's backdrop. Views + cards call `setBackgroundArt(url)` on
// hover / mount so the nearest layout cross-fades to that image. Uses
// provide/inject rather than a Pinia store because the setter is purely
// presentational and doesn't need persistence.
import { useTimeoutFn } from "@vueuse/core";
import { inject, provide, ref } from "vue";

export type SetBackgroundArt = (url: string | null) => void;

export const BACKGROUND_ART_KEY = "r-v2-set-background-art" as const;

export function useBackgroundArt(): SetBackgroundArt {
  // Fall back to a no-op when used outside AppLayout (e.g. in Storybook)
  // so components can call it unconditionally.
  return inject<SetBackgroundArt>(BACKGROUND_ART_KEY, () => undefined);
}

// Without a dwell, a cursor crossing the gallery starts one 700ms fade per
// card and they collide as flashes; the latest call wins after it.
const BG_HOVER_DWELL_MS = 80;

/** Provides the setter to descendants and returns the two cross-fading layers. */
export function provideBackgroundArt() {
  const layerA = ref<string | null>(null);
  const layerB = ref<string | null>(null);
  const activeLayer = ref<"a" | "b">("a");

  const swap = useTimeoutFn(
    (url: string | null) => {
      if (activeLayer.value === "a") {
        layerB.value = url;
        activeLayer.value = "b";
      } else {
        layerA.value = url;
        activeLayer.value = "a";
      }
    },
    BG_HOVER_DWELL_MS,
    { immediate: false },
  );

  const setBackgroundArt: SetBackgroundArt = (url) => {
    const current = activeLayer.value === "a" ? layerA.value : layerB.value;
    if (current === url) {
      swap.stop();
      return;
    }
    swap.start(url);
  };
  provide(BACKGROUND_ART_KEY, setBackgroundArt);

  return { layerA, layerB, activeLayer };
}
