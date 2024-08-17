import type { AxiosProgressEvent } from "axios";
import { defineStore } from "pinia";

export default defineStore("upload", {
  state: () => ({
    filenames: [] as string[],
    progress: 0,
    total: 0,
    loaded: 0,
    rate: 0,
    finished: false,
  }),
  actions: {
    start(filenames: string[]) {
      this.filenames = filenames;
      this.finished = false;
      this.reset();
    },
    update(progressEvent: AxiosProgressEvent) {
      this.progress = progressEvent.progress || this.progress;
      this.total = progressEvent.total || this.total;
      this.loaded = progressEvent.loaded;
      this.rate = progressEvent.rate || this.rate;
      this.finished = progressEvent.loaded === progressEvent.total;
    },
    reset() {
      this.progress = 0;
      this.total = 0;
      this.loaded = 0;
      this.rate = 0;
    },
    clear() {
      this.reset();
      this.filenames = [];
      this.finished = true;
    },
  },
});
