import { storybookTest } from "@storybook/addon-vitest/vitest-plugin";
import vue from "@vitejs/plugin-vue";
import { playwright } from "@vitest/browser-playwright";
import vuetify from "vite-plugin-vuetify";
import { defineConfig } from "vitest/config";
import { appAliases } from "./scripts/aliases";
import { platformIconManifest } from "./scripts/platformIconManifest";
import { trimMdiIcons } from "./scripts/trimMdiIcons";

export default defineConfig({
  plugins: [
    vue(),
    vuetify({ autoImport: true }),
    platformIconManifest(),
    trimMdiIcons(),
  ],
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
      // Every story renders in real Chromium, where addon-a11y runs axe on it
      // with layout (so color-contrast is checked) and honours `parameters.a11y`.
      {
        extends: true,
        plugins: [storybookTest({ configDir: ".storybook" })],
        // A dependency found mid-run reloads the page and silently drops the
        // tests in flight, so pre-bundle everything stories reach up front.
        optimizeDeps: {
          include: ["vuetify/components/*", "country-flag-emoji-polyfill"],
        },
        // Mirrors vite.config.js, which the router's `process.env.BASE_URL` needs.
        define: { "process.env": {} },
        test: {
          name: "storybook",
          browser: {
            enabled: true,
            headless: true,
            provider: playwright(),
            // Storybook's default `rommDesktopMd` viewport.
            viewport: { width: 1024, height: 768 },
            instances: [{ browser: "chromium" }],
          },
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
