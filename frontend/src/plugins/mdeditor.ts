import { config, XSSPlugin } from "md-editor-v3";

export async function configureMDEditor() {
  config({
    editorExtensions: {
      screenfull: {
        instance: { isEnabled: false },
      },
    },
    // Release notes and user notes embed raw HTML (e.g. <img>); XSSPlugin sanitizes it.
    markdownItConfig(md) {
      md.set({ html: true });
    },
    markdownItPlugins(plugins) {
      return [
        ...plugins,
        {
          type: "xss",
          plugin: XSSPlugin,
          options: {},
        },
      ];
    },
  });
}
