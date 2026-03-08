import type {
  Body_add_platform_api_platforms_post as AddPlatformInput,
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

async function updatePlatform({ platform }: { platform: Platform }) {
  return api.put<Platform>(`/platforms/${platform.id}`, {
    custom_name: platform.custom_name,
    aspect_ratio: platform.aspect_ratio,
  });
}

async function deletePlatform({ platform }: { platform: Platform }) {
  return api.delete(`/platforms/${platform.id}`);
}

export default {
  uploadPlatform,
  getPlatforms,
  getPlatform,
  getSupportedPlatforms,
  updatePlatform,
  deletePlatform,
};
