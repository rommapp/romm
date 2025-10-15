import { defineStore } from "pinia";
import type {
  ScanTaskStatusResponse,
  ConversionTaskStatusResponse,
  CleanupTaskStatusResponse,
  UpdateTaskStatusResponse,
} from "@/__generated__";
import type { TaskInfo } from "@/__generated__/models/TaskInfo";
import tasksApi from "@/services/api/task";

export default defineStore("tasks", {
  state: () => ({
    watcherTasks: [] as TaskInfo[],
    scheduledTasks: [] as TaskInfo[],
    manualTasks: [] as TaskInfo[],
    taskStatuses: [] as (
      | ScanTaskStatusResponse
      | ConversionTaskStatusResponse
      | CleanupTaskStatusResponse
      | UpdateTaskStatusResponse
    )[],
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
    async fetchTaskStatus(): Promise<
      (
        | ScanTaskStatusResponse
        | ConversionTaskStatusResponse
        | CleanupTaskStatusResponse
        | UpdateTaskStatusResponse
      )[]
    > {
      try {
        const response = await tasksApi.getTaskStatus();
        this.taskStatuses = response.data;
        return this.taskStatuses;
      } catch (error) {
        console.error("Error fetching task status: ", error);
        this.taskStatuses = [];
        return [];
      }
    },
  },
});
