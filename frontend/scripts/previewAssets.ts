// Serves frontend/assets (emulator runtimes, icons) under `vite preview`, as
// the dev server and the Docker image do; the build leaves it out of dist/.
import { fileURLToPath } from "node:url";
import sirv from "sirv";
import type { Plugin } from "vite";

const ASSETS_DIR = fileURLToPath(new URL("../assets", import.meta.url));

export function previewAssets(): Plugin {
  return {
    name: "romm:preview-assets",
    configurePreviewServer(server) {
      // `dev` skips indexing the tree up front, since assets/romm can link to a
      // whole library. A miss falls through to the build's own dist/assets.
      server.middlewares.use("/assets", sirv(ASSETS_DIR, { dev: true }));
    },
  };
}
