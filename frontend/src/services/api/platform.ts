import type { MessageResponse } from "@/__generated__";
import api from "@/services/api/index";
import type { Platform } from "@/stores/platforms";

export const platformApi = api;

async function uploadPlatform({
  fsSlug,
}: {
  fsSlug: string;
}): Promise<{ data: Platform }> {
  return api.post("/platforms", { fs_slug: fsSlug });
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
  return api.put(`/platforms/${platform.id}`, platform);
}

async function deletePlatform({
  platform,
}: {
  platform: Platform;
}): Promise<{ data: MessageResponse }> {
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
