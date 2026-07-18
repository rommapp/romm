// useDebugMode — master toggle for the v2 debug overlay.
//
// localStorage-only on purpose: the debug overlay is a per-device developer
// aid, not a preference you want propagated to your account across every
// machine. That's why it lives here as a singleton ref (mirroring the
// useCrtMode / useUiVersion pattern) instead of inside UI_SETTINGS_KEYS,
// which two-way syncs to the backend.
import { useLocalStorage } from "@vueuse/core";

const enabled = useLocalStorage("settings.v2.debugMode", false);

export function useDebugMode() {
  return { enabled };
}
