import type {
  Body_add_state_api_states_post as AddStateInput,
  Body_update_state_api_states__id__put as UpdateStateInput,
  DetailedRomSchema,
  StateSchema,
} from "@/__generated__";
import api from "@/services/api";
import { buildFormInput } from "@/utils/formData";

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
}) {
  const promises = statesToUpload.map(({ stateFile, screenshotFile }) => {
    const formData = buildFormInput<UploadStateInput>([
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

export default {
  uploadStates,
  updateState,
  deleteStates,
};
