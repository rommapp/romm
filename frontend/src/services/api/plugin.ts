import type { PluginSchema } from "@/__generated__";
import api from "@/services/api";

type Plugin = PluginSchema;

export const pluginApi = api;

async function getPlugins() {
  return api.get<Plugin[]>("/plugins");
}

export default { getPlugins };
