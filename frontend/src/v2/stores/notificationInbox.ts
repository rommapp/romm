// notificationInbox (v2): the signed-in user's notifications, newest first,
// kept current by `installNotificationInbox`.
import { defineStore } from "pinia";
import type {
  NotificationCreatePayload,
  NotificationIdsPayload,
  NotificationSchema,
} from "@/__generated__";
import notificationApi from "@/services/api/notification";

// Bumped by reset(), so a list requested for the previous user is dropped.
let generation = 0;

// Marks what this tab sends, so its push stays quiet. Math.random, as
// crypto.randomUUID needs a secure context and RomM is often served over http.
const TAB_ID = Math.random().toString(36).slice(2);

// No ids stands for every notification, as it does in the API.
type NotificationIds = NotificationIdsPayload["ids"];

/** An idempotent edit of the list, returning it untouched when nothing matches. */
type Change = (list: NotificationSchema[]) => NotificationSchema[];

// A fetch's response can predate what changed while it was in flight, so each
// pending fetch collects those changes and replays them onto its result.
const pendingFetches = new Set<Change[]>();

function added(notification: NotificationSchema): Change {
  return (list) => {
    if (list.some((n) => n.id === notification.id)) return list;
    const at = list.findIndex((n) => n.id < notification.id);
    return at === -1
      ? [...list, notification]
      : [...list.slice(0, at), notification, ...list.slice(at)];
  };
}

function removed(ids: NotificationIds): Change {
  const targets = ids && new Set(ids);
  return (list) => {
    const kept = targets ? list.filter((n) => !targets.has(n.id)) : [];
    return kept.length === list.length ? list : kept;
  };
}

function withReadAt(ids: NotificationIds, readAt: string | null): Change {
  const targets = ids && new Set(ids);
  // Marking read touches only the unread; unmarking only what it marked.
  const matches = (n: NotificationSchema) =>
    (readAt ? !n.read_at : !!n.read_at) && (!targets || targets.has(n.id));
  return (list) =>
    list.some(matches)
      ? list.map((n) => (matches(n) ? { ...n, read_at: readAt } : n))
      : list;
}

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
    apply(change: Change) {
      this.notifications = change(this.notifications);
      pendingFetches.forEach((changes) => changes.push(change));
    },

    async fetch() {
      const requested = generation;
      const changes: Change[] = [];
      pendingFetches.add(changes);
      try {
        const { data } = await notificationApi.getNotifications();
        if (requested !== generation) return;
        this.notifications = changes.reduce(
          (list, change) => change(list),
          data,
        );
        this.loaded = true;
      } finally {
        pendingFetches.delete(changes);
      }
    },

    /** Adds a notification; false when it was already here. */
    receive(notification: NotificationSchema): boolean {
      if (this.notifications.some((n) => n.id === notification.id)) {
        return false;
      }
      this.apply(added(notification));
      return true;
    },

    /** Notifies the signed-in user, marked as coming from this tab. */
    async send(payload: Omit<NotificationCreatePayload, "recipients">) {
      const { data } = await notificationApi.create({
        ...payload,
        data: { ...payload.data, origin_tab: TAB_ID },
      });
      this.receive(data[0]);
    },

    sentFromThisTab(notification: NotificationSchema): boolean {
      return notification.data.origin_tab === TAB_ID;
    },

    applyRead(ids: NotificationIds) {
      this.apply(withReadAt(ids, new Date().toISOString()));
    },

    applyDismissed(ids: NotificationIds) {
      this.apply(removed(ids));
    },

    // Optimistic: the rows read at once, and unread again if the server refuses.
    async markRead(ids: number[]) {
      if (ids.length === 0) return;
      this.applyRead(ids);
      try {
        await notificationApi.markRead(ids);
      } catch (error) {
        this.apply(withReadAt(ids, null));
        throw error;
      }
    },

    // Optimistic: the row goes at once and comes back if the server refuses.
    async dismiss(id: number) {
      const notification = this.notifications.find((n) => n.id === id);
      this.applyDismissed([id]);
      try {
        await notificationApi.dismiss(id);
      } catch (error) {
        if (notification) this.apply(added(notification));
        throw error;
      }
    },

    async dismissAll() {
      await notificationApi.dismissAll();
      this.applyDismissed(null);
    },

    reset() {
      generation += 1;
      this.notifications = [];
      this.loaded = false;
    },
  },
});
