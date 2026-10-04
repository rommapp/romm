import vue from "@vitejs/plugin-vue";
import vuetify from "vite-plugin-vuetify";
import { defineConfig } from "vitest/config";
import { appAliases } from "./scripts/aliases";
import { platformIconManifest } from "./scripts/platformIconManifest";

export default defineConfig({
  plugins: [vue(), vuetify({ autoImport: true }), platformIconManifest()],
  resolve: {
    alias: appAliases,
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
          // Vitest empties CSS imports; `?raw` ones are plain text we read.
          css: { include: [/\.css\?raw$/] },
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
