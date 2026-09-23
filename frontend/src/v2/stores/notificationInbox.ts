// notificationInbox (v2): the signed-in user's notifications, newest first,
// kept current by `installNotificationInbox`.
import { defineStore } from "pinia";
import type {
  NotificationCreatePayload,
  NotificationIdsPayload,
  NotificationSchema,
} from "@/__generated__";
import notificationApi from "@/services/api/notification";

// No ids stands for every notification, as it does in the API.
type NotificationIds = NotificationIdsPayload["ids"];

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

    // Both leave the list untouched when nothing matches, as when a tab's own
    // change comes back over the socket, so the view doesn't re-render.
    applyRead(ids: NotificationIds) {
      const targets = ids && new Set(ids);
      const matches = (n: NotificationSchema) =>
        !n.read_at && (!targets || targets.has(n.id));
      if (!this.notifications.some(matches)) return;
      const readAt = new Date().toISOString();
      this.notifications = this.notifications.map((n) =>
        matches(n) ? { ...n, read_at: readAt } : n,
      );
    },

    applyDismissed(ids: NotificationIds) {
      const targets = ids && new Set(ids);
      const kept = targets
        ? this.notifications.filter((n) => !targets.has(n.id))
        : [];
      if (kept.length !== this.notifications.length) this.notifications = kept;
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
