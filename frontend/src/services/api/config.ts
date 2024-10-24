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

async function addPlatformVersionConfig({
  fsSlug,
  slug,
}: {
  fsSlug: string;
  slug: string;
}): Promise<{ data: MessageResponse }> {
  return api.post("/config/system/versions", { fs_slug: fsSlug, slug: slug });
}

async function deletePlatformVersionConfig({
  fsSlug,
}: {
  fsSlug: string;
}): Promise<{ data: MessageResponse }> {
  return api.delete(`/config/system/versions/${fsSlug}`);
}

async function addExclusion({
  exclusionValue,
  exclusionType,
}: {
  exclusionValue: string;
  exclusionType: string;
}): Promise<{ data: MessageResponse }> {
  return api.post("/config/exclude", {
    exclusion_value: exclusionValue,
    exclusion_type: exclusionType,
  });
}

export default {
  addPlatformBindConfig,
  deletePlatformBindConfig,
  addPlatformVersionConfig,
  deletePlatformVersionConfig,
  addExclusion,
};
