import type { StateSchema } from "@/__generated__";
import { api } from "@/services/api";
import type { Rom } from "@/stores/roms";

export const api_state = api;

async function uploadStates({ rom, states }: { rom: Rom; states: File[] }) {
  let formData = new FormData();
  states.forEach((state) => formData.append("states", state));

  return api.post("/states", formData, {
    headers: {
      "Content-Type": "multipart/form-data",
    },
    params: { rom_id: rom.id },
  });
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
  deleteStates,
};
