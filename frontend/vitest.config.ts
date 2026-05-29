import vue from "@vitejs/plugin-vue";
import { URL, fileURLToPath } from "node:url";
import vuetify from "vite-plugin-vuetify";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [vue(), vuetify({ autoImport: true })],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
      "@v2": fileURLToPath(new URL("./src/v2", import.meta.url)),
    },
  },
  test: {
    environment: "happy-dom",
    globals: true,
    setupFiles: ["./vitest.setup.ts"],
    include: ["src/**/*.{test,spec}.ts", "test/**/*.{test,spec}.ts"],
    server: {
      deps: {
        inline: ["vuetify"],
      },
    },
  },
});
