import type {
  Body_add_save_api_saves_post as AddSaveInput,
  Body_update_save_api_saves__id__put as UpdateSaveInput,
  DetailedRomSchema,
  SaveSchema,
} from "@/__generated__";
import api from "@/services/api";
import { buildFormInput } from "@/utils/formData";

export const saveApi = api;

async function uploadSaves({
  rom,
  savesToUpload,
  emulator,
}: {
  rom: DetailedRomSchema;
  savesToUpload: AddSaveInput[];
  emulator?: string;
}) {
  const promises = savesToUpload.map(({ saveFile, screenshotFile }) => {
    const formData = buildFormInput<AddSaveInput>([
      ["saveFile", saveFile],
      ["screenshotFile", screenshotFile],
    ]);

    return new Promise<SaveSchema>((resolve, reject) => {
      api
        .post<SaveSchema>("/saves", formData, {
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
}) {
  const formData = buildFormInput<UpdateSaveInput>([
    ["saveFile", saveFile],
    ["screenshotFile", screenshotFile],
  ]);

  return api.put<SaveSchema>(`/saves/${save.id}`, formData);
}

async function deleteSaves({ saves }: { saves: SaveSchema[] }) {
  return api.post<number[]>("/saves/delete", { saves: saves.map((s) => s.id) });
}

export default {
  uploadSaves,
  updateSave,
  deleteSaves,
};
