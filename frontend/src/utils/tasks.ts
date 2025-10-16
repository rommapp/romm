import type {
  ScanTaskStatusResponse,
  ConversionTaskStatusResponse,
  CleanupTaskStatusResponse,
  UpdateTaskStatusResponse,
  GenericTaskStatusResponse,
  WatcherTaskStatusResponse,
  JobStatus,
  TaskType,
} from "@/__generated__";

export type TaskStatusResponse =
  | ScanTaskStatusResponse
  | ConversionTaskStatusResponse
  | CleanupTaskStatusResponse
  | UpdateTaskStatusResponse
  | GenericTaskStatusResponse
  | WatcherTaskStatusResponse;

export const TaskStatusItem: Record<
  JobStatus,
  { color: string; icon: string; status: string; text: string }
> = {
  queued: {
    color: "orange",
    icon: "mdi-clock-outline",
    status: "queued",
    text: "Queued",
  },
  started: {
    color: "blue",
    icon: "mdi-loading",
    status: "primary",
    text: "Running",
  },
  finished: {
    color: "green",
    icon: "mdi-check-circle",
    status: "success",
    text: "Completed",
  },
  failed: {
    color: "red",
    icon: "mdi-alert-circle",
    status: "error",
    text: "Failed",
  },
  stopped: {
    color: "grey",
    icon: "mdi-stop-circle",
    status: "grey",
    text: "Stopped",
  },
  canceled: {
    color: "grey",
    icon: "mdi-stop-circle",
    status: "grey",
    text: "Canceled",
  },
  deferred: {
    color: "grey",
    icon: "mdi-clock-outline",
    status: "grey",
    text: "Deferred",
  },
  scheduled: {
    color: "grey",
    icon: "mdi-clock-outline",
    status: "grey",
    text: "Scheduled",
  },
};

export const TaskTypeItem: Record<TaskType, { title: string; icon: string }> = {
  scan: { title: "Scan", icon: "mdi-magnify-scan" },
  conversion: { title: "Conversion", icon: "mdi-image-multiple" },
  cleanup: { title: "Cleanup", icon: "mdi-broom" },
  update: { title: "Update", icon: "mdi-update" },
  watcher: { title: "Watcher", icon: "mdi-eye" },
  generic: { title: "Task", icon: "mdi-help-circle" },
};
