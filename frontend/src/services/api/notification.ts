import type {
  NotificationCreatePayload,
  NotificationSchema,
} from "@/__generated__";
import api from "@/services/api";

async function getNotifications() {
  return api.get<NotificationSchema[]>("/notifications");
}

async function create(payload: NotificationCreatePayload) {
  return api.post<NotificationSchema[]>("/notifications", payload);
}

async function markRead(ids: number[] | null) {
  return api.post("/notifications/read", { ids });
}

async function dismiss(id: number) {
  return api.delete(`/notifications/${id}`);
}

async function dismissAll() {
  return api.delete("/notifications");
}

export default {
  getNotifications,
  create,
  markRead,
  dismiss,
  dismissAll,
};
