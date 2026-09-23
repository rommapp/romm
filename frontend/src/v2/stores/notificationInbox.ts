// notificationInbox (v2) — the signed-in user's notifications, newest first,
// kept current by `installNotificationInbox`.
import { defineStore } from "pinia";
import type {
  NotificationCreatePayload,
  NotificationSchema,
} from "@/__generated__";
import notificationApi from "@/services/api/notification";

// `null` stands for every notification, as it does in the API.
type NotificationIds = number[] | null;

export default defineStore("v2NotificationInbox", {
  state: () => ({
    notifications: [] as NotificationSchema[],
    loaded: false,
  }),

  getters: {
    unreadCount: (state): number =>
      state.notifications.filter((n) => !n.read_at).length,
  },

  actions: {
    async fetch() {
      const { data } = await notificationApi.getNotifications();
      this.notifications = data;
      this.loaded = true;
    },

    /** Adds a notification; false when it was already here. */
    receive(notification: NotificationSchema): boolean {
      if (this.notifications.some((n) => n.id === notification.id)) {
        return false;
      }
      this.notifications = [notification, ...this.notifications];
      return true;
    },

    /** Notifies the signed-in user and returns what was stored. */
    async send(
      payload: Omit<NotificationCreatePayload, "recipients">,
    ): Promise<NotificationSchema> {
      const { data } = await notificationApi.create(payload);
      return data[0];
    },

    applyRead(ids: NotificationIds, readAt = new Date().toISOString()) {
      const targets = ids && new Set(ids);
      this.notifications = this.notifications.map((n) =>
        !n.read_at && (!targets || targets.has(n.id))
          ? { ...n, read_at: readAt }
          : n,
      );
    },

    applyDismissed(ids: NotificationIds) {
      if (!ids) {
        this.notifications = [];
        return;
      }
      const targets = new Set(ids);
      this.notifications = this.notifications.filter((n) => !targets.has(n.id));
    },

    async markRead(ids: number[]) {
      if (ids.length === 0) return;
      this.applyRead(ids);
      await notificationApi.markRead(ids);
    },

    // Optimistic: the row goes at once and comes back if the server refuses.
    async dismiss(id: number) {
      const before = this.notifications;
      this.applyDismissed([id]);
      try {
        await notificationApi.dismiss(id);
      } catch (error) {
        this.notifications = before;
        throw error;
      }
    },

    async dismissAll() {
      await notificationApi.dismissAll();
      this.applyDismissed(null);
    },

    reset() {
      this.notifications = [];
      this.loaded = false;
    },
  },
});
