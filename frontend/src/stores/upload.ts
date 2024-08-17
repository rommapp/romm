import { defineStore } from "pinia";

type UploadingRom = {
  filename: string;
  progress: number;
  finished?: boolean;
};

export default defineStore("upload", {
  state: () => ({
    value: [] as UploadingRom[],
  }),
  actions: {
    add(filename: string) {
      this.value = [...this.value, { filename, progress: 0 }];
    },
    update({ filename, progress }: { filename: string; progress: number }) {
      this.value = this.value.map((rom) =>
        rom.filename === filename
          ? { ...rom, progress, finished: Math.ceil(progress) === 100 }
          : rom,
      );
    },
    clear() {
      this.value = [] as UploadingRom[];
    },
  },
});
