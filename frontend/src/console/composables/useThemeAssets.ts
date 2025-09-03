import { computed, type ComputedRef } from "vue";
import {
  resolveAsset,
  type AssetType,
  type SupportedFormat,
} from "@/console/utils/assetResolver";
import { useConsoleTheme } from "@/stores/consoleTheme";

// provides reactive asset paths for theme-aware components
// this is the single source of truth for all asset path resolution
export function useThemeAssets() {
  const themeStore = useConsoleTheme();

  function getAssetPath(
    assetType: AssetType,
    filename: string,
    preferredFormat: SupportedFormat = "svg",
  ): ComputedRef<string> {
    return computed(() =>
      resolveAsset(assetType, filename, preferredFormat, themeStore.themeName),
    );
  }

  function getSystemImagePath(
    platformSlug: string,
    preferredFormat: SupportedFormat = "svg",
  ): ComputedRef<string> {
    return computed(() =>
      resolveAsset(
        "systems",
        platformSlug,
        preferredFormat,
        themeStore.themeName,
      ),
    );
  }

  function getBezelImagePath(
    platformSlug: string,
    preferredFormat: SupportedFormat = "png",
  ): ComputedRef<string> {
    return computed(() =>
      resolveAsset(
        "bezels",
        platformSlug,
        preferredFormat,
        themeStore.themeName,
      ),
    );
  }

  function getBackgroundImagePath(
    backgroundName: string = "background",
    preferredFormat: SupportedFormat = "svg",
  ): ComputedRef<string> {
    return computed(() =>
      resolveAsset(
        "backgrounds",
        backgroundName,
        preferredFormat,
        themeStore.themeName,
      ),
    );
  }

  return {
    getAssetPath,
    getSystemImagePath,
    getBezelImagePath,
    getBackgroundImagePath,
    themeName: computed(() => themeStore.themeName),
  };
}
