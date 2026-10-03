import { fileURLToPath } from "node:url";
import type { Alias } from "vite";

const fromRoot = (path: string) =>
  fileURLToPath(new URL(`../${path}`, import.meta.url));

// One list for the app build and vitest, so tests resolve imports the way the
// app does. Storybook picks it up through vite.config.js.
export const appAliases: Alias[] = [
  { find: "@", replacement: fromRoot("src") },
  { find: "@v2", replacement: fromRoot("src/v2") },
  // Every md-editor import, v1 included, gets the XSS config on first load.
  // tsconfig.app.json maps it too, so go-to-definition lands on the plugin.
  { find: /^md-editor-v3$/, replacement: fromRoot("src/plugins/mdeditor.ts") },
];
