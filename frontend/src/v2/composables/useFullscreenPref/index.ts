// useFullscreenPref — shared "start in fullscreen on play?" preference.
// Backs both player views (EmulatorJS + Ruffle) so flipping it in one
// place persists across the other. Uses the same localStorage key v1
// writes to (`emulation.fullScreenOnPlay`), so the toggle stays in sync
// with the v1 UI.
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
