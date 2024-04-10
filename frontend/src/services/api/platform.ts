import type { MessageResponse, PlatformSchema } from "@/__generated__";
import api from "@/services/api/index";

export const platformApi = api;

async function uploadPlatform({
  fsSlug,
}: {
  fsSlug: string;
}): Promise<{ data: PlatformSchema }> {
  return api.post("/platforms", { fs_slug: fsSlug });
}

async function getPlatforms(): Promise<{ data: PlatformSchema[] }> {
  return api.get("/platforms");
}

async function getPlatform(
  id: number | undefined
): Promise<{ data: PlatformSchema }> {
  return api.get(`/platforms/${id}`);
}

async function getSupportedPlatforms(): Promise<{ data: PlatformSchema[] }> {
  return api.get("/platforms/supported");
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
  getSupportedPlatforms,
  deletePlatform,
};
