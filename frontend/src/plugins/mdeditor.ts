import { config, XSSPlugin } from "md-editor-v3";

export function configureMDEditor() {
  config({
    editorExtensions: {
      screenfull: {
        instance: { isEnabled: false },
      },
      // Charts are off, and without an instance md-editor fetches echarts from unpkg on mount.
      echarts: {
        instance: {},
      },
    },
    // Release notes and user notes embed raw HTML (e.g. <img>); XSSPlugin sanitizes it.
    markdownItConfig(md) {
      md.set({ html: true });
    },
    markdownItPlugins(plugins) {
      return [
        ...plugins.filter((p) => p.type !== "echarts"),
        {
          type: "xss",
          plugin: XSSPlugin,
          options: {},
        },
      ];
    },
  });
}

// Each md-editor consumer imports this module, so the config lands in their lazy chunk.
configureMDEditor();
