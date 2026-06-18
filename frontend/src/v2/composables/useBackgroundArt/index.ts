// useBackgroundArt
//
// Tiny pass-through for the AppLayout's backdrop setter. Views + cards call
// `setBackgroundArt(url)` on hover / mount so the nearest layout cross-fades
// to that image. Uses provide/inject rather than a Pinia store because the
// setter is purely presentational and doesn't need persistence.
import { inject } from "vue";

export type SetBackgroundArt = (url: string | null) => void;

export const BACKGROUND_ART_KEY = "r-v2-set-background-art" as const;

export function useBackgroundArt(): SetBackgroundArt {
  // Fall back to a no-op when used outside AppLayout (e.g. in Storybook)
  // so components can call it unconditionally.
  return inject<SetBackgroundArt>(BACKGROUND_ART_KEY, () => undefined);
}
