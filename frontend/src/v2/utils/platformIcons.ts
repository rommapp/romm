import shippedIcons from "virtual:platform-icons";

const PLATFORM_ICON_DIR = "/assets/platforms";
export const DEFAULT_PLATFORM_ICON = `${PLATFORM_ICON_DIR}/default.ico`;

export function platformSlugKey(slug: string): string {
  return slug.trim().toLowerCase();
}

/** Public URL of the icon shipped for `slug`, or null when none ships. */
export function shippedPlatformIconUrl(slug: string): string | null {
  const file = shippedIcons.get(platformSlugKey(slug));
  return file ? `${PLATFORM_ICON_DIR}/${file}` : null;
}

/** Icon URL for a platform: `slug` first, then `fsSlug`, then the default. */
export function platformIconUrl(
  slug?: string | null,
  fsSlug?: string | null,
): string {
  return (
    (slug && shippedPlatformIconUrl(slug)) ||
    (fsSlug && shippedPlatformIconUrl(fsSlug)) ||
    DEFAULT_PLATFORM_ICON
  );
}
