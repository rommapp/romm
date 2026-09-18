import type { StorybookConfig } from "@storybook/vue3-vite";
import { fileURLToPath, URL } from "node:url";

const config: StorybookConfig = {
  // Only pick up v2 stories. The v1 UI is frozen and does not ship stories.
  stories: ["../src/v2/**/*.stories.@(js|jsx|ts|tsx)", "../src/v2/**/*.mdx"],
  addons: [
    "@storybook/addon-docs",
    "@storybook/addon-a11y",
    "@storybook/addon-themes",
  ],
  framework: {
    name: "@storybook/vue3-vite",
    options: {},
  },
  async viteFinal(cfg) {
    cfg.resolve ??= {};
    const srcRoot = fileURLToPath(new URL("../src", import.meta.url));
    const stubFile = (name: string) =>
      fileURLToPath(new URL(`./stubs/${name}`, import.meta.url));

    // Stub aliases first so `@/services/api` does not resolve through `@`.
    cfg.resolve.alias = [
      {
        find: /^@\/services\/api(?:\/.*)?$/,
        replacement: stubFile("api.ts"),
      },
      {
        find: /^@\/services\/socket(?:\.ts)?$/,
        replacement: stubFile("socket.ts"),
      },
      {
        find: /^@\/services\/pending-asset(?:\.ts)?$/,
        replacement: stubFile("pending-asset.ts"),
      },
      {
        find: /^@\/services\/cache(?:\/.*)?$/,
        replacement: stubFile("cache.ts"),
      },
      { find: "@", replacement: srcRoot },
      {
        find: "@v2",
        replacement: fileURLToPath(new URL("../src/v2", import.meta.url)),
      },
    ];
    // Drop VitePWA and romm:precompress; they belong to the app build.
    function isBlocked(name: string) {
      return name.startsWith("vite-plugin-pwa") || name === "romm:precompress";
    }
    function keep(plugin: unknown): unknown[] {
      if (!plugin) return [];
      if (Array.isArray(plugin)) {
        return plugin.flatMap(keep);
      }
      if (typeof plugin !== "object") return [plugin];
      const name = (plugin as { name?: string }).name ?? "";
      return isBlocked(name) ? [] : [plugin];
    }
    cfg.plugins = (cfg.plugins ?? []).flatMap(keep) as typeof cfg.plugins;
    cfg.server ??= {};
    // Do not inherit the app `/api` proxy. Ignore the local ROM library
    // (watching it exhausts inotify).
    cfg.server.proxy = {};
    cfg.server.watch ??= {};
    cfg.server.watch.ignored = [
      ...(Array.isArray(cfg.server.watch.ignored)
        ? cfg.server.watch.ignored
        : cfg.server.watch.ignored
          ? [cfg.server.watch.ignored]
          : []),
      "**/assets/romm/**",
      "**/node_modules/**",
      "**/.git/**",
    ];
    return cfg;
  },
};

export default config;
