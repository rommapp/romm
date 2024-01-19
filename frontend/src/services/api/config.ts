import type { MessageResponse } from "@/__generated__";
import api from "@/services/api/index";

export const configApi = api;

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
  return api.delete(`/config/system/platforms/${fsSlug}`);
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
  addExclusion,
};
