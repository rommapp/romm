import type { AxiosResponse } from "axios";
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
  return api.post<void, AxiosResponse<void>, PlatformBindingPayload>(
    "/config/system/platforms",
    { fs_slug: fsSlug, slug },
  );
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
  return api.post<void, AxiosResponse<void>, PlatformBindingPayload>(
    "/config/system/versions",
    { fs_slug: fsSlug, slug },
  );
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
  return api.post<void, AxiosResponse<void>, ExclusionPayload>(
    "/config/exclude",
    {
      exclusion_value: exclusionValue,
      exclusion_type: exclusionType,
    },
  );
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
