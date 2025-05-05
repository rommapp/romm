import api from "@/services/api/index";
import type { DetailedRom } from "@/stores/roms";
import type { StateSchema } from "@/__generated__";

export const stateApi = api;

async function uploadStates({
  rom,
  statesToUpload,
  emulator,
}: {
  rom: DetailedRom;
  statesToUpload: {
    stateFile: File;
    screenshotFile?: File;
  }[];
  emulator?: string;
}): Promise<PromiseSettledResult<StateSchema>[]> {
  const promises = statesToUpload.map(({ stateFile, screenshotFile }) => {
    const formData = new FormData();
    formData.append("stateFile", stateFile);
    if (screenshotFile) {
      formData.append("screenshotFile", screenshotFile);
    }

    return new Promise<StateSchema>((resolve, reject) => {
      api
        .post("/states", formData, {
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
  stateFile: File;
  screenshotFile?: File;
}): Promise<{ data: StateSchema }> {
  const formData = new FormData();
  formData.append("stateFile", stateFile);
  if (screenshotFile) formData.append("screenshotFile", screenshotFile);

  return api.put(`/states/${state.id}`, formData);
}

async function deleteStates({
  states,
}: {
  states: StateSchema[];
}): Promise<{ data: number[] }> {
  return api.post("/states/delete", {
    states: states.map((s) => s.id),
  });
}

export default {
  uploadStates,
  updateState,
  deleteStates,
};
