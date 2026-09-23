const PLATFORM_ICON_DIR = "/assets/platforms";
export const DEFAULT_PLATFORM_ICON = `${PLATFORM_ICON_DIR}/default.ico`;

/** slug → filename. `.svg` wins when both exist. */
export function indexShippedPlatformIcons(
  paths: readonly string[],
): Map<string, string> {
  const index = new Map<string, string>();
  for (const path of paths) {
    const file = path.split("/").pop();
    if (!file) continue;
    const match = /^(.*)\.(svg|ico)$/i.exec(file);
    if (!match) continue;
    const slug = match[1].toLowerCase();
    const ext = match[2].toLowerCase();
    if (ext === "svg" || !index.has(slug)) index.set(slug, file);
  }
  return index;
}

/** Public URL if we shipped a file for `slug`, else `null` (no GET). */
export function resolveShippedPlatformIconUrl(
  slug: string,
  index: ReadonlyMap<string, string>,
): string | null {
  const file = index.get(slug.toLowerCase());
  return file ? `${PLATFORM_ICON_DIR}/${file}` : null;
}

const shippedIcons = indexShippedPlatformIcons(
  Object.keys(
    import.meta.glob("../../../../assets/platforms/*.{svg,ico}", {
      eager: true,
      query: "?url",
      import: "default",
    }),
  ),
);

export function shippedPlatformIconUrl(slug: string): string | null {
  return resolveShippedPlatformIconUrl(slug, shippedIcons);
}
