import vue from "@vitejs/plugin-vue";
import { URL, fileURLToPath } from "node:url";
import vuetify from "vite-plugin-vuetify";
import { defineConfig } from "vitest/config";
import { platformIconManifest } from "./scripts/platformIconManifest";

export default defineConfig({
  plugins: [vue(), vuetify({ autoImport: true }), platformIconManifest()],
  resolve: {
    alias: [
      {
        find: "@",
        replacement: fileURLToPath(new URL("./src", import.meta.url)),
      },
      {
        find: "@v2",
        replacement: fileURLToPath(new URL("./src/v2", import.meta.url)),
      },
      // Every md-editor import, v1 included, gets the XSS config on first load.
      {
        find: /^md-editor-v3$/,
        replacement: fileURLToPath(
          new URL("./src/plugins/mdeditor.ts", import.meta.url),
        ),
      },
    ],
  },
  test: {
    server: {
      deps: {
        inline: ["vuetify", "@vueuse/integrations"],
      },
    },
    projects: [
      {
        extends: true,
        test: {
          name: "app",
          environment: "happy-dom",
          globals: true,
          setupFiles: ["./vitest.setup.ts"],
          // Each test starts with fresh mock call history, original `vi.spyOn`
          // targets, globals and env.
          clearMocks: true,
          restoreMocks: true,
          unstubGlobals: true,
          unstubEnvs: true,
          include: ["src/**/*.{test,spec}.ts", "test/**/*.{test,spec}.ts"],
        },
      },
      // Lint rules parse source text, so they skip the app's DOM and Storybook setup.
      {
        test: {
          name: "eslint-plugin-romm",
          environment: "node",
          globals: true,
          include: ["eslint-plugin-romm/**/*.test.ts"],
        },
      },
    ],
  },
});
