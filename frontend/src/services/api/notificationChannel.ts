import type {
  EmailChannelCreatePayload,
  NotificationChannelSchema,
  NotificationChannelTestResult,
  NotificationChannelUpdatePayload,
  WebhookChannelCreatePayload,
} from "@/__generated__";
import api from "@/services/api";

async function getChannels() {
  return api.get<NotificationChannelSchema[]>("/notification-channels");
}

async function create(
  payload: WebhookChannelCreatePayload | EmailChannelCreatePayload,
) {
  return api.post<NotificationChannelSchema>("/notification-channels", payload);
}

async function update(id: number, payload: NotificationChannelUpdatePayload) {
  return api.patch<NotificationChannelSchema>(
    `/notification-channels/${id}`,
    payload,
  );
}

async function remove(id: number) {
  return api.delete(`/notification-channels/${id}`);
}

async function test(id: number) {
  return api.post<NotificationChannelTestResult>(
    `/notification-channels/${id}/test`,
  );
}

async function confirm(id: number, code: string) {
  return api.post<NotificationChannelSchema>(
    `/notification-channels/${id}/confirm`,
    { code },
  );
}

async function resendCode(id: number) {
  return api.post(`/notification-channels/${id}/resend-code`);
}

export default {
  getChannels,
  create,
  update,
  remove,
  test,
  confirm,
  resendCode,
};
