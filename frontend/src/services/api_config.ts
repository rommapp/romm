import type { MessageResponse } from "@/__generated__";
import { api } from "@/services/api";

export const api_config = api;

async function addPlatformBindConfig({
  fsSlug,
  slug,
}: {
  fsSlug: string;
  slug: string;
}): Promise<{ data: MessageResponse }> {
  return api.post("/config/system/platforms", { fs_slug: fsSlug, slug: slug });
}

async function deletePlatformBindConfig({
  fsSlug,
}: {
  fsSlug: string;
}): Promise<{ data: MessageResponse }> {
  return api.delete("/config/system/platforms", { data: { fs_slug: fsSlug } });
}

export default {
  addPlatformBindConfig,
  deletePlatformBindConfig,
};
