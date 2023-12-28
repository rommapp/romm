import { defineStore } from "pinia";

export default defineStore("runningTasks", {
  state: () => ({ value: false }),

  actions: {
    set(runningTasks) {
      this.value = runningTasks;
    },
  },
});