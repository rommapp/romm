// Drops the @mdi/font icon rules nothing in src/ names, and fails the build on
// an mdi-* name the stylesheet does not define.
import { readdirSync, readFileSync } from "node:fs";
import { extname, join } from "node:path";
import type { Plugin } from "vite";

const ICON_NAME = /mdi-[a-z0-9-]+/g;
// Also matches the bare "mdi-" left where a name is joined at runtime.
const ICON_TOKEN = /(?<![\w-])mdi-[a-z0-9-]*/g;
const ICON_RULE = /\.(mdi-[a-z0-9-]+)::before\s*\{[^}]*\}/g;
const ICON_CLASS = /\.(mdi-[a-z0-9-]+)/g;

function sourceFiles(root: string): { path: string; text: string }[] {
  return readdirSync(join(root, "src"), { recursive: true, encoding: "utf8" })
    .filter((path) => [".vue", ".ts"].includes(extname(path)))
    .map((path) => ({
      path: join("src", path),
      text: readFileSync(join(root, "src", path), "utf8"),
    }));
}

export function usedIconNames(root: string): Set<string> {
  return new Set(
    sourceFiles(root).flatMap(({ text }) => text.match(ICON_NAME) ?? []),
  );
}

/** Each mdi-* token in src/ outside tests that `css` defines no class for, as "path:line token". */
export function unknownIconNames(root: string, css: string): string[] {
  const classes = new Set(
    [...css.matchAll(ICON_CLASS)].map(([, name]) => name),
  );
  return sourceFiles(root)
    .filter(({ path }) => !path.endsWith(".test.ts"))
    .flatMap(({ path, text }) =>
      [...text.matchAll(ICON_TOKEN)]
        .filter(([token]) => !classes.has(token))
        .map(({ 0: token, index }) => {
          const line = text.slice(0, index).split("\n").length;
          return `${path}:${line} ${token}`;
        }),
    );
}

export function trimIconCss(css: string, used: Set<string>): string {
  return css.replace(ICON_RULE, (rule, name) => (used.has(name) ? rule : ""));
}

export function trimMdiIcons(): Plugin {
  let root = "";
  let used = new Set<string>();
  return {
    name: "romm:trim-mdi-icons",
    apply: "build",
    enforce: "pre",
    configResolved(config) {
      root = config.root;
      used = usedIconNames(root);
    },
    transform(code, id) {
      if (!id.endsWith("@mdi/font/css/materialdesignicons.css")) return null;
      const unknown = unknownIconNames(root, code);
      if (unknown.length) {
        this.error(
          `@mdi/font has no class for these names. Fix the name, or write it in full instead of building it at runtime:\n${unknown.join("\n")}`,
        );
      }
      return { code: trimIconCss(code, used), map: null };
    },
  };
}
