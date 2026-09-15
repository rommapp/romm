import type {
  Body_add_save_api_saves_post as AddSaveInput,
  Body_update_save_api_saves__id__put as UpdateSaveInput,
  DetailedRomSchema,
  SaveSchema,
} from "@/__generated__";
import api from "@/services/api";
import { buildFormInput } from "@/utils/formData";

export const saveApi = api;

// The slot sync clients (Argosy, Tender) file automatic progress under. A
// null slot is an archival manual upload that is never paired with devices.
export const AUTOSAVE_SLOT = "autosave";
// Mirrors the backend's SAVE_SLOT_MAX_LENGTH so the field stops at the limit.
export const SAVE_SLOT_MAX_LENGTH = 255;

type SaveUploadInput = Omit<AddSaveInput, "saveFile" | "screenshotFile"> & {
  saveFile: File;
  screenshotFile?: File;
};

type UpdateSaveUploadInput = Omit<
  UpdateSaveInput,
  "saveFile" | "screenshotFile"
> & {
  saveFile: File;
  screenshotFile?: File;
};

async function uploadSaves({
  rom,
  savesToUpload,
  emulator,
  deviceId,
  slot,
  autocleanup,
  overwrite,
}: {
  rom: DetailedRomSchema;
  savesToUpload: SaveUploadInput[];
  emulator?: string;
  deviceId?: string;
  slot?: string;
  autocleanup?: boolean;
  /** Skip the stale-device conflict check and the content-hash dedupe. */
  overwrite?: boolean;
}) {
  const promises = savesToUpload.map(({ saveFile, screenshotFile }) => {
    const formData = buildFormInput<SaveUploadInput>([
      ["saveFile", saveFile],
      ["screenshotFile", screenshotFile],
    ]);

    return new Promise<SaveSchema>((resolve, reject) => {
      api
        .post<SaveSchema>("/saves", formData, {
          headers: {
            "Content-Type": "multipart/form-data",
          },
          params: {
            rom_id: rom.id,
            emulator,
            device_id: deviceId,
            slot,
            autocleanup,
            overwrite,
          },
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
  deviceId,
}: {
  save: SaveSchema;
  saveFile: UpdateSaveUploadInput["saveFile"];
  screenshotFile?: UpdateSaveUploadInput["screenshotFile"];
  deviceId?: string;
}) {
  const formData = buildFormInput<UpdateSaveUploadInput>([
    ["saveFile", saveFile],
    ["screenshotFile", screenshotFile],
  ]);

  return api.put<SaveSchema>(`/saves/${save.id}`, formData, {
    params: { device_id: deviceId },
  });
}

async function deleteSaves({ saves }: { saves: SaveSchema[] }) {
  return api.post<number[]>("/saves/delete", { saves: saves.map((s) => s.id) });
}

async function setSaveVisibility({
  id,
  isPublic,
}: {
  id: number;
  isPublic: boolean;
}) {
  return api.put<SaveSchema>(`/saves/${id}/visibility`, {
    is_public: isPublic,
  });
}

export default {
  uploadSaves,
  updateSave,
  deleteSaves,
  setSaveVisibility,
};
