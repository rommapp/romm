import type { StorybookConfig } from "@storybook/vue3-vite";
import { fileURLToPath, URL } from "node:url";

const config: StorybookConfig = {
  // Only pick up v2 stories — the v1 UI is frozen and does not ship stories.
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
    // Ensure path aliases match the main app's Vite config so stories can
    // import from @/ and @v2/ without surprises.
    cfg.resolve ??= {};
    cfg.resolve.alias = {
      ...(cfg.resolve.alias as Record<string, string>),
      "@": fileURLToPath(new URL("../src", import.meta.url)),
      "@v2": fileURLToPath(new URL("../src/v2", import.meta.url)),
    };
    // The main app's Vite config registers VitePWA and viteStaticCopy; both
    // are app-build concerns (service worker, ROM patcher assets) and have
    // no place in Storybook. Flatten the plugin tree (vite plugins can be
    // arrays of plugins) and strip anything PWA or static-copy related.
    function isBlocked(name: string) {
      return (
        name.startsWith("vite-plugin-pwa") ||
        name === "vite-plugin-static-copy" ||
        name.startsWith("vite-plugin-static-copy")
      );
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
    // The runtime ROM library lives under `frontend/assets/romm/resources/`
    // (cover art, RetroAchievement badges, …). Watching it exhausts the
    // system's inotify handles (ENOSPC) and is irrelevant to Storybook.
    cfg.server ??= {};
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
