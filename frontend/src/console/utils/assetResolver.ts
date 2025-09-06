import { useConsoleTheme } from "@/console/composables/useConsoleTheme";

// supported image formats
export type SupportedFormat = "svg" | "png" | "jpg" | "jpeg" | "webp";

export type AssetType = "systems" | "bezels" | "backgrounds";

// cache to avoid redundant checks
const assetCache = new Map<string, string>();

export function resolveAsset(
  assetType: AssetType,
  filename: string,
  preferredFormat: SupportedFormat = "svg",
  themeName?: string,
): string {
  const themeStore = useConsoleTheme();
  const currentTheme = themeName || themeStore.themeName;
  const baseFilename = filename.replace(/\.(svg|png|jpg|jpeg|webp)$/i, "");

  // check cache first
  const cacheKey = `${currentTheme}:${assetType}:${baseFilename}`;
  if (assetCache.has(cacheKey)) {
    return assetCache.get(cacheKey)!;
  }

  const assetPath = `/assets/console/${currentTheme}/${assetType}/${baseFilename}.${preferredFormat}`;
  assetCache.set(cacheKey, assetPath);
  return assetPath;
}

export function clearAssetCache(): void {
  assetCache.clear();
}
