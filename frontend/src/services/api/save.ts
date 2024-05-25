import type { SaveSchema, UploadedSavesResponse } from "@/__generated__";
import api from "@/services/api/index";
import type { DetailedRom } from "@/stores/roms";

export const saveApi = api;

async function uploadSaves({
  rom,
  saves,
  emulator,
}: {
  rom: DetailedRom;
  saves: File[];
  emulator?: string;
}): Promise<{ data: UploadedSavesResponse }> {
  let formData = new FormData();
  saves.forEach((save) => formData.append("saves", save));

  return api.post("/saves", formData, {
    headers: {
      "Content-Type": "multipart/form-data",
    },
    params: { rom_id: rom.id, emulator },
  });
}

async function updateSave({
  save,
  file,
}: {
  save: SaveSchema;
  file: File;
}): Promise<{ data: SaveSchema }> {
  var formData = new FormData();
  formData.append("file", file);

  return api.put(`/saves/${save.id}`, formData);
}

async function deleteSaves({
  saves,
  deleteFromFs,
}: {
  saves: SaveSchema[];
  deleteFromFs: boolean;
}) {
  return api.post("/saves/delete", {
    saves: saves.map((s) => s.id),
    delete_from_fs: deleteFromFs,
  });
}

export default {
  deleteSaves,
  updateSave,
  uploadSaves,
};
