import { defineStore } from "pinia";
import type { TaskInfo } from "@/__generated__/models/TaskInfo";
import tasksApi from "@/services/api/task";
import type { TaskStatusResponse } from "@/utils/tasks";

// Several triggers (poll, visibility, a run button) can overlap status
// requests. A success applies unless a newer one already has, and a failure
// clears the list only when no newer request is pending.
let latestStatusRequest = 0;
let latestAppliedStatus = 0;

export default defineStore("tasks", {
  state: () => ({
    watcherTasks: [] as TaskInfo[],
    scheduledTasks: [] as TaskInfo[],
    manualTasks: [] as TaskInfo[],
    taskStatuses: [] as TaskStatusResponse[],
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
    async fetchTaskStatus(): Promise<TaskStatusResponse[]> {
      const request = ++latestStatusRequest;
      try {
        const response = await tasksApi.getTaskStatus();
        if (request > latestAppliedStatus) {
          latestAppliedStatus = request;
          this.taskStatuses = response.data;
        }
        return response.data;
      } catch (error) {
        console.error("Error fetching task status: ", error);
        if (request === latestStatusRequest) this.taskStatuses = [];
        return [];
      }
    },
  },
});
