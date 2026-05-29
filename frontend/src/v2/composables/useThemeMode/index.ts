// useThemeMode — reactive `isLight` / `isDark` driven by the same source
// of truth RomM.vue uses for the global theme: the `settings.theme`
// localStorage key (`"auto" | "dark" | "light"`) combined with the
// system `prefers-color-scheme: dark` media query when `"auto"`.
//
// Consumers that need to know whether the current UI is on a light or
// dark surface (md-editor, PDF viewer, …) read from here instead of
// reaching into any specific theming framework's runtime.
//
// Module-level singleton refs — every consumer shares the same
// localStorage and media-query listeners.
import { useLocalStorage, usePreferredDark } from "@vueuse/core";
import { computed, type ComputedRef } from "vue";

const themeSetting = useLocalStorage<"auto" | "dark" | "light">(
  "settings.theme",
  "auto",
);
const systemPrefersDark = usePreferredDark();

const isDark = computed(() => {
  if (themeSetting.value === "dark") return true;
  if (themeSetting.value === "light") return false;
  return systemPrefersDark.value;
});

const isLight = computed(() => !isDark.value);

export function useThemeMode(): {
  isLight: ComputedRef<boolean>;
  isDark: ComputedRef<boolean>;
} {
  return { isLight, isDark };
}
