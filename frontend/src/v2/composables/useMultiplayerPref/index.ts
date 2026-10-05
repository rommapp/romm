// useMultiplayerPref, the shared "open this session to other players?" preference.
// Persisted the way the neighbouring fullscreen switch is, so the launch
// screen remembers how the user plays. The consequence is deliberate: leaving
// it on keeps later sessions advertised until it is turned off again.
import type { RemovableRef } from "@vueuse/core";
import { useUserLocalStorage } from "@/composables/useUserLocalStorage";

const multiplayerOnPlay = useUserLocalStorage<boolean>(
  "emulation.multiplayerOnPlay",
  false,
);

export function useMultiplayerPref(): {
  multiplayerOnPlay: RemovableRef<boolean>;
} {
  return { multiplayerOnPlay };
}
