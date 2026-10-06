export type PlayerSlug =
  "stream" | "jsdos" | "ejs" | "pico8" | "easyrpg" | "ruffle";

/** The route of a ROM's player. */
export function playerPath(romId: number, slug: PlayerSlug): string {
  return `/rom/${romId}/${slug}`;
}
