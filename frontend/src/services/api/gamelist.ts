import api from "@/services/api";

export const gamelistApi = api;

async function exportGamelist({
  platformIds,
  romIds,
}: {
  platformIds: number[];
  romIds?: number[];
}): Promise<Blob> {
  const params = new URLSearchParams();
  platformIds.forEach((id) => params.append("platform_ids", id.toString()));
  if (romIds) {
    romIds.forEach((id) => params.append("rom_ids", id.toString()));
  }

  const response = await api.post(
    `/v1/gamelist/export?${params.toString()}`,
    {},
    {
      responseType: "blob",
    },
  );

  return response.data;
}

async function exportPlatformGamelist({
  platformId,
  romIds,
}: {
  platformId: number;
  romIds?: number[];
}): Promise<Blob> {
  const params = new URLSearchParams();
  if (romIds) {
    romIds.forEach((id) => params.append("rom_ids", id.toString()));
  }

  const response = await api.post(
    `/v1/gamelist/export/platform/${platformId}?${params.toString()}`,
    {},
    {
      responseType: "blob",
    },
  );

  return response.data;
}

async function previewPlatformGamelist({
  platformId,
  romIds,
}: {
  platformId: number;
  romIds?: number[];
}): Promise<{
  platform: {
    id: number;
    name: string;
    fs_slug: string;
  };
  rom_count: number;
  roms: Array<{
    id: number;
    name: string;
    fs_name: string;
    has_cover: boolean;
    has_screenshots: boolean;
    has_summary: boolean;
  }>;
}> {
  const params = new URLSearchParams();
  if (romIds) {
    romIds.forEach((id) => params.append("rom_ids", id.toString()));
  }

  const response = await api.get(
    `/v1/gamelist/export/platform/${platformId}/preview?${params.toString()}`,
  );
  return response.data;
}

export default {
  exportGamelist,
  exportPlatformGamelist,
  previewPlatformGamelist,
};
