import type { InjectionKey } from "vue";

type MdEditorModule = typeof import("md-editor-v3");

export type MdEditorLoader = () => Promise<MdEditorModule>;

// Wrappers inject this so stories can swap in a never-resolving loader to
// show the skeleton. The app never provides it, so the real loader is used.
export const MD_EDITOR_LOADER: InjectionKey<MdEditorLoader> =
  Symbol("MD_EDITOR_LOADER");

let loading: Promise<MdEditorModule> | null = null;

/** Loads md-editor-v3 on first use and configures it once. The library pulls in
 *  CodeMirror and markdown-it, so it stays out of the entry chunk.
 */
export function loadMdEditor(): Promise<MdEditorModule> {
  loading ??= (async () => {
    const [mdEditor] = await Promise.all([
      import("md-editor-v3"),
      import("md-editor-v3/lib/style.css"),
    ]);
    mdEditor.config({
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
            plugin: mdEditor.XSSPlugin,
            options: {},
          },
        ];
      },
    });
    return mdEditor;
  })().catch((error: unknown) => {
    // Let a later caller retry after a failed chunk load.
    loading = null;
    throw error;
  });
  return loading;
}
