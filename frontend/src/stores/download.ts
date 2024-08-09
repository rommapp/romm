import { defineStore } from "pinia";

export default defineStore("download", {
  state: () => ({
    value: [] as number[],
    filesToDownload: [] as string[],
  }),

  actions: {
    add(id: number) {
      this.value.push(id);
    },
    remove(id: number) {
      this.value.splice(this.value.indexOf(id), 1);
    },
    clear() {
      this.value = [] as number[];
      this.filesToDownload = [] as string[];
    },
  },
});
