import { readdirSync, readFileSync } from "node:fs";
import { extname, join, sep } from "node:path";

const SCAN_DIRS = ["src"];
const SCAN_EXTS = new Set([".vue", ".ts"]);
const SKIP_DIRS = new Set(["node_modules", "dist", ".output"]);

// Icons Vuetify draws itself (checkbox, radio, clear button, file input...).
const SCAN_FILES = ["node_modules/vuetify/lib/iconsets/mdi.js"];

// Named by the backend at runtime (backend/endpoints/responses/notification.py).
// Listed here because the production build sees frontend/ alone.
export const BACKEND_ICONS = ["mdi-sync"];

export function readSourceText(root: string): string {
  const files = SCAN_FILES.map((file) => join(root, file));
  for (const dir of SCAN_DIRS) {
    const paths = readdirSync(join(root, dir), {
      recursive: true,
      encoding: "utf8",
    });
    for (const path of paths) {
      if (path.split(sep).some((part) => SKIP_DIRS.has(part))) continue;
      if (SCAN_EXTS.has(extname(path))) files.push(join(root, dir, path));
    }
  }
  const texts = files.map((file) => readFileSync(file, "utf8"));
  return [...texts, ...BACKEND_ICONS].join("\n");
}

// The allow list: every icon name that appears in the source text.
export function buildIconAllowList(sourceText: string): string[] {
  return [...new Set(sourceText.match(/mdi-[a-z0-9-]+/g))].sort();
}

// Only `.mdi-name::before { content: ... }` can be dropped. Unsure means keep.
export function isUnusedIcon(rule: string, allowList: string[]): boolean {
  const text = rule.trim();
  const open = text.indexOf("{");
  if (!text.startsWith(".mdi-") || open === -1) return false;

  const selector = text.slice(0, open).trim();
  if (!selector.endsWith("::before")) return false;

  const name = selector.slice(1, selector.lastIndexOf("::before"));
  if (name === "mdi-") return false;
  if (!/^[a-z0-9-]+$/.test(name)) return false;

  const declarations = text.slice(open + 1).split(";");
  if (!declarations.some((d) => d.trim().startsWith("content:"))) return false;

  // Substring match: mdi-account stays when mdi-account-circle is allowed.
  return !allowList.some((allowed) => allowed.includes(name));
}

// Split at "}" so each piece is one rule.
export function dropUnusedIcons(css: string, allowList: string[]): string {
  return css
    .split("}")
    .filter((rule) => !isUnusedIcon(rule, allowList))
    .join("}");
}

// The @font-face lists eot, woff2, woff and ttf. Keep only woff2.
export function keepOnlyWoff2(css: string): string {
  const urlEnd = css.indexOf('") format("woff2")');
  const urlStart = css.lastIndexOf("../fonts/", urlEnd);
  if (urlEnd === -1 || urlStart === -1) {
    throw new Error("No woff2 url in the @mdi/font css");
  }
  const file = css.slice(urlStart + "../fonts/".length, urlEnd);

  const lines = css
    .split("\n")
    .filter((line) => !line.trim().startsWith("src:"));
  const family = lines.findIndex((line) =>
    line.includes('font-family: "Material Design Icons"'),
  );
  if (family === -1) throw new Error("No font-family in the @mdi/font css");

  const src = `  src: url("../../node_modules/@mdi/font/fonts/${file}") format("woff2");`;
  lines.splice(family + 1, 0, src);
  return lines.join("\n");
}

// The package's .map file is not copied, so its pointer would dangle.
export function dropSourceMapComment(css: string): string {
  return css
    .split("\n")
    .filter((line) => !line.startsWith("/*# sourceMappingURL="))
    .join("\n");
}

// The package CSS has CRLF line endings in places, and git stores LF.
export const toLf = (text: string) => text.replaceAll("\r\n", "\n");

export function trimIconCss(packageCss: string, allowList: string[]): string {
  const css = dropUnusedIcons(toLf(packageCss), allowList);
  return keepOnlyWoff2(dropSourceMapComment(css));
}
