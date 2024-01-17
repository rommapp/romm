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

async function addExclusion({
  exclude,
  exclusion,
}: {
  exclude: string;
  exclusion: string;
}): Promise<{ data: MessageResponse }> {
  return api.post("/config/exclude", {
    exclude: exclude,
    exclusion: exclusion,
  });
}



export default {
  addPlatformBindConfig,
  deletePlatformBindConfig,
  addExclusion
};
