import type { SaveSchema } from "@/__generated__";
import { api } from "@/services/api";
import type { Rom } from "@/stores/roms";

export const api_save = api;

async function uploadSaves({ rom, saves }: { rom: Rom; saves: File[] }) {
  let formData = new FormData();
  saves.forEach((save) => formData.append("saves", save));
  console.log(saves);
  return api.post("/saves", formData, {
    headers: {
      "Content-Type": "multipart/form-data",
    },
    params: { rom_id: rom.id },
  });
}

async function deleteSaves({
  saves,
  deleteFromFs,
}: {
  saves: SaveSchema[];
  deleteFromFs: boolean;
}) {
  return api.delete("/saves", {
    data: {
      saves: saves.map((s) => s.id),
      delete_from_fs: deleteFromFs,
    },
  });
}

export default {
  deleteSaves,
  uploadSaves,
};
