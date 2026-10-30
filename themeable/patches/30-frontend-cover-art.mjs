// Lets a theme recolor RomM's generated placeholder covers or replace them with its own art.
import { COVER_VARS, STYLESHEET_ID } from "../lib/client.mjs";

export const file = "frontend/src/v2/utils/covers.ts";
export const description = "Read the active theme's placeholder cover colors and artwork in the cover generator";
const MARKER = "// romm-themeable: cover art";

function replaceAll(text, from, to, what) {
  if (!text.includes(from)) throw new Error(`expected ${what}`);
  return text.split(from).join(to);
}

export function apply(text) {
  if (text.includes(MARKER)) return text;
  const anchor = 'import { colorCoverArt } from "@/v2/tokens";';
  let out = replaceAll(
    text,
    anchor,
    `${anchor}

${MARKER}
// The compiled theme sets these CSS variables; without them RomM's own art is used.
let themeableCovers: {
  palette: { base: string; shade: string; warm: string; icon: string };
  art: { missing: string[]; unmatched: string[] };
} | null = null;
function themeable() {
  if (themeableCovers) return themeableCovers;
  const css = typeof document === "undefined" ? null : getComputedStyle(document.documentElement);
  const read = (name: string) => css?.getPropertyValue(name).trim() ?? "";
  const list = (name: string) => read(name).split(/\\s+/).filter(Boolean);
  const covers = {
    palette: {
      base: read(${JSON.stringify(COVER_VARS.base)}) || colorCoverArt.base,
      shade: read(${JSON.stringify(COVER_VARS.shade)}) || colorCoverArt.shade,
      warm: read(${JSON.stringify(COVER_VARS.warm)}) || colorCoverArt.warm,
      icon: read(${JSON.stringify(COVER_VARS.icon)}) || colorCoverArt.icon,
    },
    art: { missing: list(${JSON.stringify(COVER_VARS.missing)}), unmatched: list(${JSON.stringify(COVER_VARS.unmatched)}) },
  };
  // Remember them only once the theme's stylesheet has loaded, so an early cover can't fix RomM's.
  const sheet = typeof document === "undefined" ? null : (document.getElementById(${JSON.stringify(STYLESHEET_ID)}) as HTMLLinkElement | null);
  if (!sheet || sheet.sheet) themeableCovers = covers;
  return covers;
}`,
    "the colorCoverArt import",
  );
  out = replaceAll(out, "const { base, shade, warm } = colorCoverArt;", "const { base, shade, warm } = themeable().palette;", "the palette in buildArt");
  out = replaceAll(out, "fill:${colorCoverArt.icon}", "fill:${themeable().palette.icon}", "the icon fill");
  out = replaceAll(
    out,
    "return identified ? getMissingCoverImage(name) : getUnmatchedCoverImage(name);",
    `const art = themeable().art[identified ? "missing" : "unmatched"];
  if (art.length) return art[hashString(name) % art.length]!;
  return identified ? getMissingCoverImage(name) : getUnmatchedCoverImage(name);`,
    "coverPlaceholderArt's return",
  );
  return out;
}
