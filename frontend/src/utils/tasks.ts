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
import i18n from "@/locales";

const { t } = i18n.global;

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
    text: t("settings.queued"),
  },
  started: {
    color: "blue",
    icon: "mdi-loading",
    status: "primary",
    text: t("settings.running"),
  },
  finished: {
    color: "green",
    icon: "mdi-check-circle",
    status: "success",
    text: t("settings.completed"),
  },
  failed: {
    color: "red",
    icon: "mdi-alert-circle",
    status: "error",
    text: t("settings.failed"),
  },
  stopped: {
    color: "grey",
    icon: "mdi-stop-circle",
    status: "grey",
    text: t("settings.stopped"),
  },
  canceled: {
    color: "grey",
    icon: "mdi-stop-circle",
    status: "grey",
    text: t("settings.canceled"),
  },
  deferred: {
    color: "grey",
    icon: "mdi-clock-outline",
    status: "grey",
    text: t("settings.deferred"),
  },
  scheduled: {
    color: "grey",
    icon: "mdi-clock-outline",
    status: "grey",
    text: t("settings.scheduled"),
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
