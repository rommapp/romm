import { type TaskExecutionResponse, type TaskInfo } from "@/__generated__";
import api from "@/services/api";
import type { TaskStatusResponse } from "@/utils/tasks";

async function getTasks() {
  return api.get<Record<string, TaskInfo[]>>("/tasks");
}

async function getTaskById(taskId: string) {
  return api.get<TaskStatusResponse>(`/tasks/${taskId}`);
}

async function runAllTasks() {
  return api.post<TaskExecutionResponse[]>("/tasks/run");
}

async function runTask(taskName: string) {
  return api.post<TaskExecutionResponse>(`/tasks/run/${taskName}`);
}

async function getTaskStatus() {
  return api.get<TaskStatusResponse[]>("/tasks/status");
}

export default {
  getTasks,
  getTaskById,
  runAllTasks,
  runTask,
  getTaskStatus,
};
