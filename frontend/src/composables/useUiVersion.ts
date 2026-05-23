// useUiVersion — singleton ref for the v1/v2 UI toggle.
//
// vueuse's useLocalStorage creates an INDEPENDENT ref per call. Two callers
// with the same key share localStorage but not Vue reactivity within the
// same tab, so writing to one won't re-render a component reading the other.
// We create the ref ONCE at module load and everyone imports it, giving us
// true reactive cross-component state without a store.
//
// Default is "v2". v1 remains reachable for users who explicitly opt back
// via Settings → User Interface → UI version → Old UI.
import { useLocalStorage } from "@vueuse/core";

export type UiVersion = "v1" | "v2";

const uiVersion = useLocalStorage<UiVersion>("settings.uiVersion", "v2");

export function useUiVersion() {
  return uiVersion;
}
