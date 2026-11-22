import { defineStore } from "pinia";
import { ref } from "vue";
import type { PluginSchema } from "@/__generated__";
import pluginApi from "@/services/api/plugin";

/** The plugins installed beside the library, and the actions they add.
 *
 * Read once per session: the shelf is on the server's disk, so it cannot
 * change between two page loads of the same session that the user could act
 * on. A failed read leaves an empty list, which hides the actions rather than
 * offering buttons that cannot open. */
export const usePluginStore = defineStore("plugins", () => {
  const plugins = ref<PluginSchema[]>([]);
  const loaded = ref(false);

  async function load(): Promise<void> {
    if (loaded.value) return;
    loaded.value = true;
    try {
      plugins.value = (await pluginApi.getPlugins()).data ?? [];
    } catch {
      plugins.value = [];
    }
  }

  return { plugins, loaded, load };
});
