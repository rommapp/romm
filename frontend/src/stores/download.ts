import { defineStore } from "pinia";
import { type RomFileSchema } from "@/__generated__";

export default defineStore("download", {
  state: () => ({
    value: [] as number[],
    filesToDownload: [] as RomFileSchema[],
  }),

  getters: {
    fileIDsToDownload: (state) => state.filesToDownload.map((file) => file.id),
  },

  actions: {
    add(id: number) {
      this.value.push(id);
    },
    remove(id: number) {
      this.value.splice(this.value.indexOf(id), 1);
    },
    reset() {
      this.value = [] as number[];
      this.filesToDownload = [] as RomFileSchema[];
    },
  },
});
