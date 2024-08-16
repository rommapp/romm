import { defineStore } from "pinia";

type UploadingRom = {
  filename: string;
  progress: number;
};

export default defineStore("upload", {
  state: () => ({
    value: [] as UploadingRom[],
  }),

  actions: {
    add(filename: string) {
      this.value = [...this.value, { filename, progress: 0 }];
    },
    remove(fname: string) {
      this.value = this.value.filter(({ filename }) => fname !== filename);
    },
    update({ filename, progress }: { filename: string; progress: number }) {
      this.value = this.value.map((rom) =>
        rom.filename === filename ? { ...rom, progress } : rom,
      );
    },
    clear() {
      this.value = [] as UploadingRom[];
    },
  },
});
