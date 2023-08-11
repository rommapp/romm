import { defineStore } from "pinia";

export default defineStore("download", {
  state: () => ({ value: [] }),

  actions: {
    add(id) {
      this.value.push(id);
    },
    remove(id) {
      this.value.splice(this.value.indexOf(id), 1);
    },
  },
});
