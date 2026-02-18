import type {
  AddFirmwareResponse,
  Body_add_firmware_api_firmware_post as AddFirmwareInput,
  Body_delete_firmware_api_firmware_delete_post as DeleteFirmwareInput,
  FirmwareSchema,
} from "@/__generated__";
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
  const payload: AddFirmwareInput = { files };
  const formData = new FormData();
  payload.files.forEach((file) => formData.append("files", file));

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
  const payload: DeleteFirmwareInput = {
    firmware: firmware.map((s) => s.id),
    delete_from_fs: deleteFromFs,
  };
  return api.post("/firmware/delete", payload);
}

export default {
  getFirmware,
  uploadFirmware,
  deleteFirmware,
};
