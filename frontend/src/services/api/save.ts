import { default as Cookies } from "js-cookie";
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
// A keepalive request outlives its document, which is why the browser caps
// its body at 64 KB; the rest is left for the multipart framing.
export const UNLOAD_SAVE_MAX_BYTES = 60 * 1024;

/** Session saves are named after the ROM; a version updated in place keeps its name. */
export function sessionSaveFile(
  rom: { fs_name_no_ext: string },
  save: SaveSchema | null,
  bytes: ArrayBuffer,
): File {
  return new File(
    [bytes],
    save ? save.file_name : `${rom.fs_name_no_ext.trim()}.srm`,
    { type: "application/octet-stream" },
  );
}

/** A save's picture: an update keeps its name, a new one takes the save's stem. */
export function sessionScreenshotFile(
  rom: { fs_name_no_ext: string },
  save: SaveSchema | null,
  bytes: ArrayBuffer,
): File {
  return new File(
    [bytes],
    save
      ? (save.screenshot?.file_name ?? `${save.file_name_no_ext}.png`)
      : `${rom.fs_name_no_ext.trim()}.png`,
    { type: "application/octet-stream" },
  );
}

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

interface SaveVersionParams {
  rom: Pick<DetailedRomSchema, "id">;
  emulator?: string;
  deviceId?: string;
  slot?: string;
  autocleanup?: boolean;
  /** Skip the stale-device conflict check and the content-hash dedupe. */
  overwrite?: boolean;
}

function saveVersionQuery({
  rom,
  emulator,
  deviceId,
  slot,
  autocleanup,
  overwrite,
}: SaveVersionParams) {
  return {
    rom_id: rom.id,
    emulator,
    device_id: deviceId,
    slot,
    autocleanup,
    overwrite,
  };
}

function saveFormData(saveFile: File, screenshotFile?: File): FormData {
  return buildFormInput<SaveUploadInput>([
    ["saveFile", saveFile],
    ["screenshotFile", screenshotFile],
  ]);
}

async function uploadSaves({
  savesToUpload,
  ...version
}: SaveVersionParams & { savesToUpload: SaveUploadInput[] }) {
  const promises = savesToUpload.map(({ saveFile, screenshotFile }) => {
    return new Promise<SaveSchema>((resolve, reject) => {
      api
        .post<SaveSchema>("/saves", saveFormData(saveFile, screenshotFile), {
          headers: {
            "Content-Type": "multipart/form-data",
          },
          params: saveVersionQuery(version),
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

/**
 * Sends a save while the page unloads, updating `save` in place or opening a
 * version in `slot`. Nothing outlives the document to await it.
 *
 * Returns:
 *   False when the save is too big for a keepalive body.
 */
function sendSaveOnUnload({
  save,
  saveFile,
  ...version
}: SaveVersionParams & { save: SaveSchema | null; saveFile: File }): boolean {
  if (saveFile.size > UNLOAD_SAVE_MAX_BYTES) return false;
  const request = save
    ? {
        url: `/saves/${save.id}`,
        method: "PUT",
        params: { device_id: version.deviceId },
      }
    : {
        url: "/saves",
        method: "POST",
        params: saveVersionQuery({ ...version, overwrite: true }),
      };
  const csrfToken = Cookies.get("romm_csrftoken");
  void fetch(api.getUri(request), {
    method: request.method,
    body: saveFormData(saveFile),
    keepalive: true,
    credentials: "same-origin",
    headers: csrfToken ? { "x-csrftoken": csrfToken } : undefined,
  }).catch(() => undefined);
  return true;
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
  sendSaveOnUnload,
  deleteSaves,
  setSaveVisibility,
};
