// useMultiplayerPref, the shared "open this session to other players?" preference.
// Persisted the way the neighbouring fullscreen switch is, so the launch
// screen remembers how the user plays. The consequence is deliberate: leaving
// it on keeps later sessions advertised until it is turned off again.
import { useLocalStorage, type RemovableRef } from "@vueuse/core";

const multiplayerOnPlay = useLocalStorage<boolean>(
  "emulation.multiplayerOnPlay",
  false,
);

export function useMultiplayerPref(): {
  multiplayerOnPlay: RemovableRef<boolean>;
} {
  return { multiplayerOnPlay };
}
