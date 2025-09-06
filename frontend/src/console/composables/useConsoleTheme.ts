import { useLocalStorage } from "@vueuse/core";
import { defineStore } from "pinia";
import { computed } from "vue";
import useBackgroundArt from "@/console/composables/useBackgroundArt";
import { resolveAsset, clearAssetCache } from "@/console/utils/assetResolver";

export const useConsoleTheme = defineStore("consoleTheme", () => {
  const themeName = useLocalStorage("console.theme", "default");
  const availableThemes = ["default", "neon"];
  const { setSelectedBackgroundArt } = useBackgroundArt();

  function setTheme(newThemeName: string): void {
    clearAssetCache();

    themeName.value = newThemeName;

    updateThemeCSS();
    updateBackgroundCSS();
  }

  function initializeTheme(): void {
    updateThemeCSS();
    updateBackgroundCSS();
  }

  function updateThemeCSS(): void {
    // remove existing theme styles
    const existingThemeLink = document.getElementById(
      "console-theme-css",
    ) as HTMLLinkElement;
    if (existingThemeLink) {
      existingThemeLink.remove();
    }

    // add new theme CSS
    const link = document.createElement("link");
    link.id = "console-theme-css";
    link.rel = "stylesheet";
    link.href = `/assets/console/${themeName.value}/theme.css`;
    document.head.appendChild(link);
  }

  function updateBackgroundCSS(): void {
    const backgroundPath = resolveAsset(
      "backgrounds",
      "background",
      "svg",
      themeName.value,
    );
    setSelectedBackgroundArt(backgroundPath);
  }

  const themeDisplayName = computed(() => {
    switch (themeName.value) {
      case "default":
        return "Default";
      case "light":
        return "Light";
      default:
        return themeName.value;
    }
  });

  return {
    themeName,
    availableThemes,
    themeDisplayName,
    setTheme,
    initializeTheme,
    updateBackgroundCSS,
  };
});
