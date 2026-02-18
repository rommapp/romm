import type { ExclusionPayload, PlatformBindingPayload } from "@/__generated__";
import api from "@/services/api";

export const configApi = api;

async function addPlatformBindConfig({
  fsSlug,
  slug,
}: {
  fsSlug: string;
  slug: string;
}) {
  const payload: PlatformBindingPayload = { fs_slug: fsSlug, slug };
  return api.post("/config/system/platforms", payload);
}

async function deletePlatformBindConfig({ fsSlug }: { fsSlug: string }) {
  return api.delete(`/config/system/platforms/${fsSlug}`);
}

async function addPlatformVersionConfig({
  fsSlug,
  slug,
}: {
  fsSlug: string;
  slug: string;
}) {
  const payload: PlatformBindingPayload = { fs_slug: fsSlug, slug };
  return api.post("/config/system/versions", payload);
}

async function deletePlatformVersionConfig({ fsSlug }: { fsSlug: string }) {
  return api.delete(`/config/system/versions/${fsSlug}`);
}

async function addExclusion({
  exclusionValue,
  exclusionType,
}: {
  exclusionValue: string;
  exclusionType: string;
}) {
  const payload: ExclusionPayload = {
    exclusion_value: exclusionValue,
    exclusion_type: exclusionType,
  };
  return api.post("/config/exclude", payload);
}

async function deleteExclusion({
  exclusionValue,
  exclusionType,
}: {
  exclusionValue: string;
  exclusionType: string;
}) {
  return api.delete(`/config/exclude/${exclusionType}/${exclusionValue}`);
}

export default {
  addPlatformBindConfig,
  deletePlatformBindConfig,
  addPlatformVersionConfig,
  deletePlatformVersionConfig,
  addExclusion,
  deleteExclusion,
};
