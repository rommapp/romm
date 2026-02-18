import type {
  Body_add_save_api_saves_post as AddSaveInput,
  Body_delete_saves_api_saves_delete_post as DeleteSavesInput,
  Body_update_save_api_saves__id__put as UpdateSaveInput,
  DetailedRomSchema,
  SaveSchema,
} from "@/__generated__";
import api from "@/services/api";

export const saveApi = api;

async function uploadSaves({
  rom,
  savesToUpload,
  emulator,
}: {
  rom: DetailedRomSchema;
  savesToUpload: AddSaveInput[];
  emulator?: string;
}): Promise<PromiseSettledResult<SaveSchema>[]> {
  const promises = savesToUpload.map(({ saveFile, screenshotFile }) => {
    const formData = new FormData();
    if (saveFile) formData.append("saveFile", saveFile);
    if (screenshotFile) formData.append("screenshotFile", screenshotFile);

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
  saveFile: UpdateSaveInput["saveFile"];
  screenshotFile?: UpdateSaveInput["screenshotFile"];
}): Promise<{ data: SaveSchema }> {
  const formData = new FormData();
  if (saveFile) formData.append("saveFile", saveFile);
  if (screenshotFile) formData.append("screenshotFile", screenshotFile);

  return api.put(`/saves/${save.id}`, formData);
}

async function deleteSaves({
  saves,
}: {
  saves: SaveSchema[];
}): Promise<{ data: number[] }> {
  const payload: DeleteSavesInput = {
    saves: saves.map((s) => s.id),
  };
  return api.post("/saves/delete", payload);
}

export default {
  uploadSaves,
  updateSave,
  deleteSaves,
};
