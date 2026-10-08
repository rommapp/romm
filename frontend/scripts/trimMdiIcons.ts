// Drops the @mdi/font icon rules nothing in src/ (or Vuetify itself) names.
import { readdirSync, readFileSync } from "node:fs";
import { extname, join } from "node:path";
import type { Plugin } from "vite";

const ICON_NAME = /mdi-[a-z0-9-]+/g;
const ICON_RULE = /\.(mdi-[a-z0-9-]+)::before\s*\{[^}]*\}/g;

export function usedIconNames(root: string): Set<string> {
  const files = readdirSync(join(root, "src"), {
    recursive: true,
    encoding: "utf8",
  })
    .filter((path) => [".vue", ".ts"].includes(extname(path)))
    .map((path) => join(root, "src", path));
  files.push(join(root, "node_modules/vuetify/lib/iconsets/mdi.js"));
  return new Set(
    files.flatMap((file) => readFileSync(file, "utf8").match(ICON_NAME) ?? []),
  );
}

export function trimIconCss(css: string, used: Set<string>): string {
  return css.replace(ICON_RULE, (rule, name) => (used.has(name) ? rule : ""));
}

export function trimMdiIcons(): Plugin {
  let used = new Set<string>();
  return {
    name: "romm:trim-mdi-icons",
    apply: "build",
    enforce: "pre",
    configResolved(config) {
      used = usedIconNames(config.root);
    },
    transform(code, id) {
      if (!id.endsWith("@mdi/font/css/materialdesignicons.css")) return null;
      return { code: trimIconCss(code, used), map: null };
    },
  };
}
