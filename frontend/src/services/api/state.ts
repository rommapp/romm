import type {
  Body_add_state_api_states_post as AddStateInput,
  Body_update_state_api_states__id__put as UpdateStateInput,
  DetailedRomSchema,
  StateSchema,
} from "@/__generated__";
import api from "@/services/api";
import { buildFormInput } from "@/utils/formData";

export const stateApi = api;

/** States are named after the ROM and the moment the core was serialized. */
export function sessionStateName(
  rom: { fs_name_no_ext: string },
  capturedAt: Date,
): string {
  const timestamp = capturedAt
    .toISOString()
    .replace(/[:.]/g, "-")
    .replace("T", " ")
    .replace("Z", "");
  return `${rom.fs_name_no_ext.trim()} [${timestamp}]`;
}

/** A state and its picture, both named after the moment of the capture. */
export function sessionStateFiles(
  rom: { fs_name_no_ext: string },
  capturedAt: Date,
  stateBytes: ArrayBuffer,
  screenshotBytes?: ArrayBuffer,
): { stateFile: File; screenshotFile?: File } {
  const name = sessionStateName(rom, capturedAt);
  const type = "application/octet-stream";
  return {
    stateFile: new File([stateBytes], `${name}.state`, { type }),
    screenshotFile: screenshotBytes
      ? new File([screenshotBytes], `${name}.png`, { type })
      : undefined,
  };
}

type StateUploadInput = Omit<AddStateInput, "stateFile" | "screenshotFile"> & {
  stateFile: File;
  screenshotFile?: File;
};

type UpdateStateUploadInput = Omit<
  UpdateStateInput,
  "stateFile" | "screenshotFile"
> & {
  stateFile: File;
  screenshotFile?: File;
};

async function uploadStates({
  rom,
  statesToUpload,
  emulator,
}: {
  rom: DetailedRomSchema;
  statesToUpload: StateUploadInput[];
  emulator?: string;
}) {
  const promises = statesToUpload.map(({ stateFile, screenshotFile }) => {
    const formData = buildFormInput<StateUploadInput>([
      ["stateFile", stateFile],
      ["screenshotFile", screenshotFile],
    ]);

    return new Promise<StateSchema>((resolve, reject) => {
      api
        .post<StateSchema>("/states", formData, {
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

async function updateState({
  state,
  stateFile,
  screenshotFile,
}: {
  state: StateSchema;
  stateFile: UpdateStateUploadInput["stateFile"];
  screenshotFile?: UpdateStateUploadInput["screenshotFile"];
}) {
  const formData = buildFormInput<UpdateStateUploadInput>([
    ["stateFile", stateFile],
    ["screenshotFile", screenshotFile],
  ]);

  return api.put<StateSchema>(`/states/${state.id}`, formData);
}

async function deleteStates({ states }: { states: StateSchema[] }) {
  return api.post<number[]>("/states/delete", {
    states: states.map((s) => s.id),
  });
}

async function setStateVisibility({
  id,
  isPublic,
}: {
  id: number;
  isPublic: boolean;
}) {
  return api.put<StateSchema>(`/states/${id}/visibility`, {
    is_public: isPublic,
  });
}

export default {
  uploadStates,
  updateState,
  deleteStates,
  setStateVisibility,
};
