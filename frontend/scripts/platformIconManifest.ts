// Exposes the icons under assets/platforms as `virtual:platform-icons`, so
// the app can skip requests for icons that were never shipped.
import { readdirSync } from "node:fs";
import { dirname, extname } from "node:path";
import { fileURLToPath } from "node:url";
import type { Plugin } from "vite";

const VIRTUAL_ID = "virtual:platform-icons";
const RESOLVED_ID = `\0${VIRTUAL_ID}`;
const ICON_FILE = /\.(svg|ico)$/i;

/** Lowercase slug to shipped filename; `.svg` wins over `.ico` when both ship. */
export function listPlatformIcons(dir: string): Map<string, string> {
  const icons = new Map<string, string>();
  const files = readdirSync(dir, { withFileTypes: true })
    .filter((entry) => entry.isFile() && ICON_FILE.test(entry.name))
    .map((entry) => entry.name)
    .sort();
  for (const file of files) {
    const ext = extname(file);
    const slug = file.slice(0, -ext.length).toLowerCase();
    if (ext.toLowerCase() === ".svg" || !icons.has(slug)) icons.set(slug, file);
  }
  return icons;
}

export function platformIconManifest(): Plugin {
  const iconDir = fileURLToPath(
    new URL("../assets/platforms", import.meta.url),
  );
  return {
    name: "romm:platform-icon-manifest",
    resolveId(id) {
      return id === VIRTUAL_ID ? RESOLVED_ID : undefined;
    },
    load(id) {
      if (id !== RESOLVED_ID) return undefined;
      const entries = [...listPlatformIcons(iconDir)];
      return `export default new Map(${JSON.stringify(entries)});`;
    },
    // An icon added or removed while the dev server runs would otherwise
    // stay invisible until a restart.
    configureServer(server) {
      const refresh = (file: string) => {
        if (dirname(file) !== iconDir || !ICON_FILE.test(file)) return;
        const mod = server.moduleGraph.getModuleById(RESOLVED_ID);
        if (mod) server.moduleGraph.invalidateModule(mod);
        server.ws.send({ type: "full-reload" });
      };
      server.watcher.on("add", refresh);
      server.watcher.on("unlink", refresh);
    },
  };
}
