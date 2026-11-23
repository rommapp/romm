import { defineStore } from "pinia";
import { ref } from "vue";
import type { PluginSchema } from "@/__generated__";
import pluginApi from "@/services/api/plugin";

/** The plugins installed beside the library, and the actions they add.
 *
 * Read once per session: the shelf is on the server's disk, so it cannot
 * change between two page loads of the same session that the user could act
 * on. A failed read leaves an empty list, which hides the actions rather than
 * offering buttons that cannot open. Installing and removing are the two things
 * that do change it, so both re-read the shelf. */
export const usePluginStore = defineStore("plugins", () => {
  const plugins = ref<PluginSchema[]>([]);
  const loaded = ref(false);

  async function load(): Promise<void> {
    if (loaded.value) return;
    await reload();
  }

  async function reload(): Promise<void> {
    loaded.value = true;
    try {
      plugins.value = (await pluginApi.getPlugins()).data ?? [];
    } catch {
      plugins.value = [];
    }
  }

  /** Install from a URL the server fetches, or a manifest the user pasted. The
   * message is the server's own reason, so the dialog can show it. */
  async function install(source: {
    url?: string;
    manifest?: object;
  }): Promise<{ ok: boolean; message?: string }> {
    try {
      await pluginApi.addPlugin(source);
    } catch (error) {
      return { ok: false, message: refusal(error) };
    }
    await reload();
    return { ok: true };
  }

  async function remove(
    pluginId: string,
  ): Promise<{ ok: boolean; message?: string }> {
    try {
      await pluginApi.deletePlugin(pluginId);
    } catch (error) {
      return { ok: false, message: refusal(error) };
    }
    await reload();
    return { ok: true };
  }

  return { plugins, loaded, load, reload, install, remove };
});

/** The server's explanation for a refused install or removal, when it gave one. */
function refusal(error: unknown): string {
  const detail = (error as { response?: { data?: { detail?: unknown } } })
    ?.response?.data?.detail;
  return typeof detail === "string"
    ? detail
    : "The server refused that plugin.";
}
