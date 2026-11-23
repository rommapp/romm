import { defineStore } from "pinia";
import { ref } from "vue";
import type { PluginSchema, StorePluginSchema } from "@/__generated__";
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
  const store = ref<StorePluginSchema[]>([]);
  const storeLoaded = ref(false);

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

  /** Install one the curated index lists. */
  async function installFromStore(
    pluginId: string,
  ): Promise<{ ok: boolean; message?: string }> {
    try {
      await pluginApi.installFromStore(pluginId);
    } catch (error) {
      return { ok: false, message: refusal(error) };
    }
    await reload();
    return { ok: true };
  }

  /** The index itself, read when the store tab is first opened. */
  async function loadStore(): Promise<string | null> {
    if (storeLoaded.value) return null;
    storeLoaded.value = true;
    try {
      store.value = (await pluginApi.getStore()).data ?? [];
    } catch (error) {
      storeLoaded.value = false;
      return refusal(error);
    }
    return null;
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

  async function settings(
    pluginId: string,
  ): Promise<Record<string, unknown> | null> {
    try {
      return (await pluginApi.getSettings(pluginId)).data?.values ?? {};
    } catch {
      return null;
    }
  }

  async function saveSettings(
    pluginId: string,
    values: Record<string, unknown>,
  ): Promise<{ ok: boolean; message?: string }> {
    try {
      await pluginApi.saveSettings(pluginId, values);
    } catch (error) {
      return { ok: false, message: refusal(error) };
    }
    return { ok: true };
  }

  return {
    plugins,
    loaded,
    store,
    storeLoaded,
    load,
    reload,
    install,
    installFromStore,
    loadStore,
    remove,
    settings,
    saveSettings,
  };
});

/** The server's explanation for a refused install or removal, when it gave one. */
function refusal(error: unknown): string {
  const detail = (error as { response?: { data?: { detail?: unknown } } })
    ?.response?.data?.detail;
  return typeof detail === "string"
    ? detail
    : "The server refused that plugin.";
}
