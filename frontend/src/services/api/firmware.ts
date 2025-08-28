import type { FirmwareSchema, AddFirmwareResponse } from "@/__generated__";
import api from "@/services/api";

export const firmwareApi = api;

async function getFirmware({
  platformId = null,
}: {
  platformId?: number | null;
}): Promise<{ data: FirmwareSchema[] }> {
  return firmwareApi.get(`/firmware`, {
    params: {
      platform_id: platformId,
    },
  });
}

async function uploadFirmware({
  platformId,
  files,
}: {
  platformId: number;
  files: File[];
}): Promise<{ data: AddFirmwareResponse }> {
  const formData = new FormData();
  files.forEach((file) => formData.append("files", file));

  return firmwareApi.post(`/firmware`, formData, {
    headers: {
      "Content-Type": "multipart/form-data",
    },
    params: { platform_id: platformId },
  });
}

async function deleteFirmware({
  firmware,
  deleteFromFs = [],
}: {
  firmware: FirmwareSchema[];
  deleteFromFs: number[];
}) {
  return api.post("/firmware/delete", {
    firmware: firmware.map((s) => s.id),
    delete_from_fs: deleteFromFs,
  });
}

export default {
  getFirmware,
  uploadFirmware,
  deleteFirmware,
};
