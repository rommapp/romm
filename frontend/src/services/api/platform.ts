import type {
  Body_add_platform_api_platforms_post as AddPlatformInput,
  Body_update_platform_api_platforms__id__put as UpdatePlatformInput,
  PlatformSchema,
} from "@/__generated__";
import api from "@/services/api";

type Platform = PlatformSchema;

export const platformApi = api;

async function uploadPlatform({ fsSlug }: { fsSlug: string }) {
  const payload: AddPlatformInput = { fs_slug: fsSlug };
  return api.post<Platform>("/platforms", payload);
}

async function getPlatforms() {
  return api.get<Platform[]>("/platforms");
}

async function getPlatform(id: number | undefined) {
  return api.get<Platform>(`/platforms/${id}`);
}

async function getSupportedPlatforms() {
  return api.get<Platform[]>("/platforms/supported");
}

async function getFilesystemPlatforms() {
  return api.get<Platform[]>("/platforms/filesystem");
}

/**
 * Partial update. Only the fields passed here are sent, and the backend
 * leaves anything omitted untouched — so a name-only caller can't replay a
 * stale description it happened to be holding and clobber a newer value.
 */
async function updatePlatform({
  id,
  customName,
  description,
}: {
  id: number;
  customName?: string;
  description?: string;
}) {
  const payload: UpdatePlatformInput = {};
  if (customName !== undefined) payload.custom_name = customName;
  if (description !== undefined) payload.description = description;
  return api.put<Platform>(`/platforms/${id}`, payload);
}

async function deletePlatform({ platform }: { platform: Platform }) {
  return api.delete(`/platforms/${platform.id}`);
}

export default {
  uploadPlatform,
  getPlatforms,
  getPlatform,
  getSupportedPlatforms,
  getFilesystemPlatforms,
  updatePlatform,
  deletePlatform,
};
