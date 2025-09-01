import {
  type TaskExecutionResponse,
  type TaskStatusResponse,
  type TaskInfo,
} from "@/__generated__";
import api from "@/services/api";

async function getTasks(): Promise<{
  data: Record<string, TaskInfo[]>;
}> {
  return api.get("/tasks");
}

async function getTaskById(
  taskId: string,
): Promise<{ data: TaskStatusResponse }> {
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

export default {
  getTasks,
  getTaskById,
  runAllTasks,
  runTask,
};
