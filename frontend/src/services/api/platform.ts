import type { MessageResponse, PlatformSchema } from "@/__generated__";
import api from "@/services/api/index";

export const platformApi = api;

async function uploadPlatform(slug: string): Promise<{ data: MessageResponse[] }> {
  return api.post("/platforms", {"slug": slug});
}

async function getPlatforms(): Promise<{ data: PlatformSchema[] }> {
  return api.get("/platforms");
}

async function getPlatform(
  id: number | undefined
): Promise<{ data: PlatformSchema }> {
  return api.get(`/platforms/${id}`);
}

async function updatePlatform({
  platform,
}: {
  platform: PlatformSchema;
}): Promise<{ data: MessageResponse }> {
  return api.delete(`/platforms/${platform.id}`);
}

async function deletePlatform({
  platform,
}: {
  platform: PlatformSchema;
}): Promise<{ data: MessageResponse }> {
  return api.delete(`/platforms/${platform.id}`);
}

export default {
  uploadPlatform,
  getPlatforms,
  getPlatform,
  deletePlatform,
};
