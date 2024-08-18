import type { AxiosProgressEvent } from "axios";
import { defineStore } from "pinia";

class UploadingFile {
  filename: string;
  progress: number;
  total: number;
  loaded: number;
  rate: number;
  finished: boolean;

  constructor(filename: string) {
    this.filename = filename;
    this.progress = 0;
    this.total = 0;
    this.loaded = 0;
    this.rate = 0;
    this.finished = false;
  }
}

export default defineStore("upload", {
  state: () => ({
    files: [] as UploadingFile[],
  }),
  actions: {
    start(filename: string) {
      this.files = [...this.files, new UploadingFile(filename)];
    },
    update(filename: string, progressEvent: AxiosProgressEvent) {
      const file = this.files.find((f) => f.filename === filename);
      if (!file) return;

      file.progress = progressEvent.progress
        ? progressEvent.progress * 100
        : file.progress;
      file.total = progressEvent.total || file.total;
      file.loaded = progressEvent.loaded;
      file.rate = progressEvent.rate || file.rate;
      file.finished = progressEvent.loaded === progressEvent.total;
    },
    clear() {
      this.files = [];
    },
  },
});
