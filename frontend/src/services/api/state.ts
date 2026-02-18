import type {
  Body_add_state_api_states_post as AddStateInput,
  Body_delete_states_api_states_delete_post as DeleteStatesInput,
  Body_update_state_api_states__id__put as UpdateStateInput,
  DetailedRomSchema,
  StateSchema,
} from "@/__generated__";
import api from "@/services/api";

export const stateApi = api;

type UploadStateInput = AddStateInput & {
  stateFile: File;
  screenshotFile?: File;
};

type UpdateStateUploadInput = UpdateStateInput & {
  stateFile: File;
  screenshotFile?: File;
};

async function uploadStates({
  rom,
  statesToUpload,
  emulator,
}: {
  rom: DetailedRomSchema;
  statesToUpload: UploadStateInput[];
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
  stateFile: UpdateStateUploadInput["stateFile"];
  screenshotFile?: UpdateStateUploadInput["screenshotFile"];
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
  const payload: DeleteStatesInput = {
    states: states.map((s) => s.id),
  };
  return api.post("/states/delete", payload);
}

export default {
  uploadStates,
  updateState,
  deleteStates,
};
