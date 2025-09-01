import { config, XSSPlugin } from "md-editor-v3";

export async function configureMDEditor() {
  config({
    editorExtensions: {
      screenfull: {
        instance: { isEnabled: false },
      },
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
