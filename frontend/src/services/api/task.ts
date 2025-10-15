import {
  type TaskExecutionResponse,
  type ScanTaskStatusResponse,
  type ConversionTaskStatusResponse,
  type CleanupTaskStatusResponse,
  type UpdateTaskStatusResponse,
  type TaskInfo,
} from "@/__generated__";
import api from "@/services/api";

async function getTasks(): Promise<{
  data: Record<string, TaskInfo[]>;
}> {
  return api.get("/tasks");
}

async function getTaskById(taskId: string): Promise<{
  data:
    | ScanTaskStatusResponse
    | ConversionTaskStatusResponse
    | CleanupTaskStatusResponse
    | UpdateTaskStatusResponse;
}> {
  return api.get(`/tasks/${taskId}`);
}

async function runAllTasks(): Promise<{ data: TaskExecutionResponse[] }> {
  return api.post("/tasks/run");
}

async function runTask(
  taskName: string,
): Promise<{ data: TaskExecutionResponse }> {
  return api.post(`/tasks/run/${taskName}`);
}

async function getTaskStatus(): Promise<{
  data: (
    | ScanTaskStatusResponse
    | ConversionTaskStatusResponse
    | CleanupTaskStatusResponse
    | UpdateTaskStatusResponse
  )[];
}> {
  return api.get("/tasks/status");
}

export default {
  getTasks,
  getTaskById,
  runAllTasks,
  runTask,
  getTaskStatus,
};
