import { defineStore } from "pinia";

export default defineStore("runningTasks", {
  state: () => ({
    runningTasks: [] as string[],
  }),

  actions: {
    reset() {
      this.runningTasks = [];
    },
    addTask(taskEndpoint: string) {
      if (!this.runningTasks.includes(taskEndpoint)) {
        this.runningTasks.push(taskEndpoint);
      }
    },
    removeTask(taskEndpoint: string) {
      const index = this.runningTasks.indexOf(taskEndpoint);
      if (index > -1) {
        this.runningTasks.splice(index, 1);
      }
    },
    isTaskRunning(taskEndpoint: string): boolean {
      return this.runningTasks.includes(taskEndpoint);
    },
  },
});
