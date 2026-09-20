// useFullscreenPref — shared "start in fullscreen on play?" preference.
// Keyed on `emulation.fullScreenOnPlay` so the toggle stays in sync with v1.
import { useLocalStorage, type RemovableRef } from "@vueuse/core";

const fullscreenOnPlay = useLocalStorage<boolean>(
  "emulation.fullScreenOnPlay",
  true,
);

export function useFullscreenPref(): {
  fullscreenOnPlay: RemovableRef<boolean>;
} {
  return { fullscreenOnPlay };
}
