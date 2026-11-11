// Drops the @mdi/font icon rules nothing in src/ names, and the glyphs they draw.
import { mkdirSync, readdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, extname, join, relative } from "node:path";
import subsetFont from "subset-font";
import type { Plugin } from "vite";

const ICON_NAME = /mdi-[a-z0-9-]+/g;
const ICON_RULE = /\.(mdi-[a-z0-9-]+)::before\s*\{[^}]*\}/g;
const ICON_CODEPOINT = /content:\s*"\\([0-9A-Fa-f]+)"/;
const FONT_FACE = /@font-face\s*\{[^}]*\}/;
const FONT_FILE = "materialdesignicons-webfont.woff2";

export function usedIconNames(root: string): Set<string> {
  const files = readdirSync(join(root, "src"), {
    recursive: true,
    encoding: "utf8",
  })
    .filter((path) => [".vue", ".ts"].includes(extname(path)))
    .map((path) => join(root, "src", path));
  return new Set(
    files.flatMap((file) => readFileSync(file, "utf8").match(ICON_NAME) ?? []),
  );
}

export function trimIconCss(css: string, used: Set<string>): string {
  return css.replace(ICON_RULE, (rule, name) => (used.has(name) ? rule : ""));
}

/** The characters the remaining icon rules draw, one per code point. */
export function keptGlyphs(css: string): string {
  const glyphs = new Set<string>();
  for (const [rule] of css.matchAll(ICON_RULE)) {
    const hex = ICON_CODEPOINT.exec(rule)?.[1];
    if (hex) glyphs.add(String.fromCodePoint(parseInt(hex, 16)));
  }
  return [...glyphs].join("");
}

export function subsetIconFont(font: Buffer, glyphs: string): Promise<Buffer> {
  return subsetFont(font, glyphs, { targetFormat: "woff2" });
}

/** Points the stylesheet's only font source at `url`, dropping the other formats. */
export function useSubsetFont(css: string, url: string): string {
  return css.replace(
    FONT_FACE,
    `@font-face {
  font-family: "Material Design Icons";
  src: url("${url}") format("woff2");
  font-weight: normal;
  font-style: normal;
}`,
  );
}

export function trimMdiIcons(): Plugin {
  let used = new Set<string>();
  let cacheDir = "";
  return {
    name: "romm:trim-mdi-icons",
    apply: "build",
    enforce: "pre",
    configResolved(config) {
      used = usedIconNames(config.root);
      cacheDir = join(config.cacheDir, "romm-mdi");
    },
    async transform(code, id) {
      if (!id.endsWith("@mdi/font/css/materialdesignicons.css")) return null;
      const css = trimIconCss(code, used);
      const font = readFileSync(join(dirname(id), "../fonts", FONT_FILE));
      const subset = await subsetIconFont(font, keptGlyphs(css));
      mkdirSync(cacheDir, { recursive: true });
      const file = join(cacheDir, FONT_FILE);
      writeFileSync(file, subset);
      return {
        code: useSubsetFont(css, relative(dirname(id), file)),
        map: null,
      };
    },
  };
}
