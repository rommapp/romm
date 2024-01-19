import type { StateSchema } from "@/__generated__";
import api from "@/services/api/index";
import type { Rom } from "@/stores/roms";

export const stateApi = api;

async function uploadStates({
  rom,
  states,
}: {
  rom: Rom;
  states: File[];
}): Promise<{ data: { uploaded: string; states: StateSchema[] } }> {
  let formData = new FormData();
  states.forEach((state) => formData.append("states", state));

  return api.post("/states", formData, {
    headers: {
      "Content-Type": "multipart/form-data",
    },
    params: { rom_id: rom.id },
  });
}

async function updateState({
  state,
  file,
}: {
  state: StateSchema;
  file: File;
}): Promise<{ data: StateSchema }> {
  var formData = new FormData();
  formData.append("file", file);

  return api.put(`/states/${state.id}`, formData);
}

async function deleteStates({
  states,
  deleteFromFs,
}: {
  states: StateSchema[];
  deleteFromFs: boolean;
}) {
  return api.post("/states/delete", {
    states: states.map((s) => s.id),
    delete_from_fs: deleteFromFs,
  });
}

export default {
  uploadStates,
  updateState,
  deleteStates,
};
