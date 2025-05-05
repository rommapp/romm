import api from "@/services/api/index";
import type { DetailedRom } from "@/stores/roms";
import type { SaveSchema } from "@/__generated__";

export const saveApi = api;

async function uploadSaves({
  rom,
  savesToUpload,
  emulator,
}: {
  rom: DetailedRom;
  savesToUpload: {
    saveFile: File;
    screenshotFile?: File;
  }[];
  emulator?: string;
}): Promise<PromiseSettledResult<SaveSchema>[]> {
  const promises = savesToUpload.map(({ saveFile, screenshotFile }) => {
    const formData = new FormData();
    formData.append("saveFile", saveFile);
    if (screenshotFile) {
      formData.append("screenshotFile", screenshotFile);
    }

    return new Promise<SaveSchema>((resolve, reject) => {
      api
        .post("/saves", formData, {
          headers: {
            "Content-Type": "multipart/form-data",
          },
          params: { rom_id: rom.id, emulator },
        })
        .then(({ data }) => {
          resolve(data);
        })
        .catch(reject);
    });
  });

  return Promise.allSettled(promises);
}

async function updateSave({
  save,
  saveFile,
  screenshotFile,
}: {
  save: SaveSchema;
  saveFile: File;
  screenshotFile?: File;
}): Promise<{ data: SaveSchema }> {
  const formData = new FormData();
  formData.append("saveFile", saveFile);
  if (screenshotFile) formData.append("screenshotFile", screenshotFile);

  return api.put(`/saves/${save.id}`, formData);
}

async function deleteSaves({
  saves,
}: {
  saves: SaveSchema[];
}): Promise<{ data: number[] }> {
  return api.post("/saves/delete", {
    saves: saves.map((s) => s.id),
  });
}

export default {
  uploadSaves,
  updateSave,
  deleteSaves,
};
