/** trimMdiIcons: ships only the @mdi/font icons the app names, in woff2 only. */
import { extname } from "node:path";
import type { Plugin } from "vite";
import {
  buildIconAllowList,
  readSourceText,
  trimIconCss,
} from "./trim-mdi-fonts";

const MDI_CSS = "@mdi/font/css/materialdesignicons.css";
const WATCHED_EXTS = new Set([".vue", ".ts"]);

// A query import (`?raw`) wants the file untouched.
export const isMdiCss = (id: string) =>
  !id.includes("?") && id.endsWith(MDI_CSS);

const countIcons = (css: string) => css.split("content:").length - 1;

export function trimMdiIcons(): Plugin {
  let root = "";
  let isBuild = false;
  let summary = "";
  let allowList: string[] = [];

  const scan = () => buildIconAllowList(readSourceText(root));

  return {
    name: "romm:trim-mdi-icons",
    // vite:css turns the CSS into a JS module, so run before it.
    enforce: "pre",

    configResolved(config) {
      root = config.root;
      isBuild = config.command === "build";
    },

    buildStart() {
      allowList = scan();
    },

    transform(code, id) {
      if (!isMdiCss(id)) return null;

      const trimmed = trimIconCss(code, allowList);
      const icons = countIcons(trimmed);
      if (icons === 0) {
        this.error(
          `No icon rules survived trimming ${id}: the allow list had ` +
            `${allowList.length} names, scanned from ${root}/src.`,
        );
      }
      const kb = (text: string) =>
        `${Math.round(Buffer.byteLength(text) / 1024)} KB`;
      summary = `${countIcons(code)} icons -> ${icons} | ${kb(code)} -> ${kb(trimmed)}`;
      return { code: trimmed, map: null };
    },

    // Dev re-runs transform on every re-optimize, so only a build logs.
    closeBundle() {
      if (isBuild && summary) this.info(summary);
    },

    configureServer(server) {
      const onSourceChange = (path: string) => {
        if (!WATCHED_EXTS.has(extname(path))) return;
        if (!path.replaceAll("\\", "/").includes("/src/")) return;

        const next = scan();
        if (next.join() === allowList.join()) return;
        allowList = next;

        for (const [id, mod] of server.moduleGraph.idToModuleMap) {
          if (isMdiCss(id)) server.moduleGraph.invalidateModule(mod);
        }
        server.ws.send({ type: "full-reload" });
      };

      server.watcher.on("change", onSourceChange);
      server.watcher.on("add", onSourceChange);
      server.watcher.on("unlink", onSourceChange);
    },
  };
}
