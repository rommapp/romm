import type { PluginSchema } from "@/__generated__";
import api from "@/services/api";

type Plugin = PluginSchema;

export const pluginApi = api;

async function getPlugins() {
  return api.get<Plugin[]>("/plugins");
}

/** Install a plugin, either from a URL the server fetches or a manifest body. */
async function addPlugin(source: { url?: string; manifest?: object }) {
  return api.post<Plugin>("/plugins", source);
}

async function deletePlugin(pluginId: string) {
  return api.delete(`/plugins/${encodeURIComponent(pluginId)}`);
}

export default { getPlugins, addPlugin, deletePlugin };
