import type {
  AddFirmwareResponse,
  BulkOperationResponse,
  FirmwareSchema,
} from "@/__generated__";
import api from "@/services/api";

export const firmwareApi = api;

async function getFirmware({
  platformId = null,
}: {
  platformId?: number | null;
}) {
  return firmwareApi.get<FirmwareSchema[]>(`/firmware`, {
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
}) {
  const formData = new FormData();
  files.forEach((file) => formData.append("files", file));

  const { data } = await firmwareApi.post<AddFirmwareResponse>(
    `/firmware`,
    formData,
    {
      headers: {
        "Content-Type": "multipart/form-data",
      },
      params: { platform_id: platformId },
    },
  );
  return data;
}

async function deleteFirmware({
  firmware,
  deleteFromFs = [],
}: {
  firmware: FirmwareSchema[];
  deleteFromFs: number[];
}) {
  return api.post<BulkOperationResponse>("/firmware/delete", {
    firmware: firmware.map((s) => s.id),
    delete_from_fs: deleteFromFs,
  });
}

export default {
  getFirmware,
  uploadFirmware,
  deleteFirmware,
};
