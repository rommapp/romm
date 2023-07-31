import { defineStore } from "pinia";

export default defineStore("download", {
  state: () => ({ value: [] }),

  actions: {
    add(filename) {
      this.value.push(filename);
    },
    remove(filename) {
      this.value.splice(this.value.indexOf(filename), 1);
    },
  },
});
