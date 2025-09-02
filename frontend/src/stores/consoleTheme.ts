import { resolveAsset, clearAssetCache } from "@/console/utils/assetResolver";
import { defineStore } from "pinia";
import { ref, computed } from "vue";

export const useConsoleTheme = defineStore("consoleTheme", () => {
  const themeName = ref<string>("default");
  const availableThemes = ["default", "neon"];

  function setTheme(newThemeName: string): void {
    clearAssetCache();

    themeName.value = newThemeName;
    localStorage.setItem("console-theme", newThemeName);

    updateThemeCSS();
    updateBackgroundCSS();
  }

  function initializeTheme(): void {
    const savedTheme = localStorage.getItem("console-theme") || "default";

    themeName.value = savedTheme;
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
    const backgroundUrl = `url("${backgroundPath}")`;
    document.documentElement.style.setProperty(
      "--theme-background",
      backgroundUrl,
    );
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
  };
});
