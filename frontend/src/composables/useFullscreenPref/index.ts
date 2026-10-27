// useFullscreenPref: shared "start in fullscreen on play?" preference.
// Keyed on `emulation.fullScreenOnPlay` so the toggle stays in sync with v1.
import type { RemovableRef } from "@vueuse/core";
import { useUserLocalStorage } from "@/composables/useUserLocalStorage";

const fullscreenOnPlay = useUserLocalStorage<boolean>(
  "emulation.fullScreenOnPlay",
  true,
);

export function useFullscreenPref(): {
  fullscreenOnPlay: RemovableRef<boolean>;
} {
  return { fullscreenOnPlay };
}
