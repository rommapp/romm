import type {
  Body_add_platform_api_platforms_post as AddPlatformInput,
  Body_update_platform_api_platforms__id__put as UpdatePlatformInput,
  PlatformSchema,
} from "@/__generated__";
import api from "@/services/api";

type Platform = PlatformSchema;

export const platformApi = api;

async function uploadPlatform({
  fsSlug,
}: {
  fsSlug: string;
}): Promise<{ data: Platform }> {
  const payload: AddPlatformInput = { fs_slug: fsSlug };
  return api.post("/platforms", payload);
}

async function getPlatforms(): Promise<{ data: Platform[] }> {
  return api.get("/platforms");
}

async function getPlatform(
  id: number | undefined,
): Promise<{ data: Platform }> {
  return api.get(`/platforms/${id}`);
}

async function getSupportedPlatforms(): Promise<{ data: Platform[] }> {
  return api.get("/platforms/supported");
}

async function updatePlatform({
  platform,
}: {
  platform: Platform;
}): Promise<{ data: Platform }> {
  const payload: UpdatePlatformInput = {
    custom_name: platform.custom_name,
    aspect_ratio: platform.aspect_ratio,
  };
  return api.put(`/platforms/${platform.id}`, payload);
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
