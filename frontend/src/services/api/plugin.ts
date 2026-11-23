import type { PluginSchema, StorePluginSchema } from "@/__generated__";
import api from "@/services/api";

type Plugin = PluginSchema;
type StorePlugin = StorePluginSchema;

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

/** The curated index: manifests a repository maintains, by URL. */
async function getStore() {
  return api.get<StorePlugin[]>("/plugins/store");
}

async function installFromStore(pluginId: string) {
  return api.post<Plugin>(`/plugins/store/${encodeURIComponent(pluginId)}`);
}

async function getSettings(pluginId: string) {
  return api.get<{ values: Record<string, unknown> }>(
    `/plugins/${encodeURIComponent(pluginId)}/settings`,
  );
}

async function saveSettings(pluginId: string, values: Record<string, unknown>) {
  return api.put<{ values: Record<string, unknown> }>(
    `/plugins/${encodeURIComponent(pluginId)}/settings`,
    { values },
  );
}

export default {
  getPlugins,
  addPlugin,
  deletePlugin,
  getStore,
  installFromStore,
  getSettings,
  saveSettings,
};
