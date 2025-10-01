import { defineStore } from "pinia";
import type { TaskStatusResponse } from "@/__generated__";
import type { TaskInfo } from "@/__generated__/models/TaskInfo";
import tasksApi from "@/services/api/task";

export default defineStore("tasks", {
  state: () => ({
    watcherTasks: [] as TaskInfo[],
    scheduledTasks: [] as TaskInfo[],
    manualTasks: [] as TaskInfo[],
    runningTasks: [] as TaskStatusResponse[],
  }),

  actions: {
    async fetchTasks(): Promise<{
      watcherTasks: TaskInfo[];
      scheduledTasks: TaskInfo[];
      manualTasks: TaskInfo[];
    }> {
      try {
        const response = await tasksApi.getTasks();
        this.watcherTasks = response.data.watcher;
        this.scheduledTasks = response.data.scheduled;
        this.manualTasks = response.data.manual;

        return {
          watcherTasks: this.watcherTasks,
          scheduledTasks: this.scheduledTasks,
          manualTasks: this.manualTasks,
        };
      } catch (error) {
        console.error("Error fetching tasks: ", error);
        return {
          watcherTasks: [],
          scheduledTasks: [],
          manualTasks: [],
        };
      }
    },
    async fetchRunningTasks(): Promise<TaskStatusResponse[]> {
      try {
        const response = await tasksApi.getRunningTasks();
        this.runningTasks = response.data;
        return this.runningTasks;
      } catch (error) {
        console.error("Error fetching running tasks: ", error);
        this.runningTasks = [];
        return [];
      }
    },
  },
});
