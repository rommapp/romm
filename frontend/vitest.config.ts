import vue from "@vitejs/plugin-vue";
import { URL, fileURLToPath } from "node:url";
import vuetify from "vite-plugin-vuetify";
import { defineConfig } from "vitest/config";
import { platformIconManifest } from "./scripts/platformIconManifest";

export default defineConfig({
  plugins: [vue(), vuetify({ autoImport: true }), platformIconManifest()],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
      "@v2": fileURLToPath(new URL("./src/v2", import.meta.url)),
    },
  },
  test: {
    server: {
      deps: {
        inline: ["vuetify"],
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
