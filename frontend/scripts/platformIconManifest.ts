// Exposes the filenames under assets/platforms as `virtual:platform-icons`, so
// the app can skip requests for icons that were never shipped. An
// `import.meta.glob` would also emit or inline every icon into the bundle.
import { readdirSync } from "node:fs";
import type { Plugin } from "vite";

const VIRTUAL_ID = "virtual:platform-icons";
const RESOLVED_ID = `\0${VIRTUAL_ID}`;
const ICON_FILE = /\.(svg|ico)$/i;

export function listPlatformIconFiles(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true })
    .filter((entry) => entry.isFile() && ICON_FILE.test(entry.name))
    .map((entry) => entry.name)
    .sort();
}

export function platformIconManifest(dir: string): Plugin {
  return {
    name: "romm:platform-icon-manifest",
    resolveId(id) {
      return id === VIRTUAL_ID ? RESOLVED_ID : undefined;
    },
    load(id) {
      if (id !== RESOLVED_ID) return undefined;
      return `export default ${JSON.stringify(listPlatformIconFiles(dir))};`;
    },
  };
}
