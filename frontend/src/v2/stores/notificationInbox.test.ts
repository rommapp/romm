import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { NotificationSchema } from "@/__generated__";
import storeNotificationInbox from "@/v2/stores/notificationInbox";
import { makeNotification } from "@/v2/utils/notifications.fixtures";

const { create, dismiss, dismissAll, getNotifications, markRead } = vi.hoisted(
  () => ({
    create: vi.fn(),
    dismiss: vi.fn(),
    dismissAll: vi.fn(),
    getNotifications: vi.fn(),
    markRead: vi.fn(),
  }),
);

vi.mock("@/services/api/notification", () => ({
  default: { create, dismiss, dismissAll, getNotifications, markRead },
}));

function notification(
  id: number,
  overrides: Partial<NotificationSchema> = {},
): NotificationSchema {
  return makeNotification({
    id,
    kind: "task_completed",
    level: "success",
    ...overrides,
  });
}

describe("notificationInbox", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.resetAllMocks();
  });

  it("counts only the unread", async () => {
    getNotifications.mockResolvedValue({
      data: [notification(2), notification(1, { read_at: "2026-09-23" })],
    });
    const inbox = storeNotificationInbox();

    await inbox.fetch();

    expect(inbox.loaded).toBe(true);
    expect(inbox.unreadCount).toBe(1);
  });

  it("drops a list that arrives after a reset", async () => {
    let answer!: (value: unknown) => void;
    getNotifications.mockReturnValue(
      new Promise((resolve) => {
        answer = resolve;
      }),
    );
    const inbox = storeNotificationInbox();

    const pending = inbox.fetch();
    inbox.reset();
    answer({ data: [notification(1)] });
    await pending;

    expect(inbox.notifications).toEqual([]);
    expect(inbox.loaded).toBe(false);
  });

  it("puts a pushed notification first, once", () => {
    const inbox = storeNotificationInbox();
    inbox.receive(notification(1));

    expect(inbox.receive(notification(2))).toBe(true);
    expect(inbox.receive(notification(2))).toBe(false);

    expect(inbox.notifications.map((n) => n.id)).toEqual([2, 1]);
  });

  it("sends a notification marked as this tab's own", async () => {
    create.mockImplementation(async (payload) => ({
      data: [notification(5, { data: payload.data })],
    }));
    const inbox = storeNotificationInbox();

    await inbox.send({ title: "Sync finished", level: "success" });

    expect(create).toHaveBeenCalledWith({
      title: "Sync finished",
      level: "success",
      data: { origin_tab: expect.any(String) },
    });
    const [sent] = inbox.notifications;
    expect(sent.id).toBe(5);
    expect(inbox.sentFromThisTab(sent)).toBe(true);
    expect(inbox.sentFromThisTab(notification(6))).toBe(false);
  });

  it("marks read what another tab read, or everything for null", () => {
    const inbox = storeNotificationInbox();
    inbox.notifications = [notification(1), notification(2), notification(3)];

    inbox.applyRead([2]);
    expect(inbox.unreadCount).toBe(2);

    inbox.applyRead(null);
    expect(inbox.unreadCount).toBe(0);
  });

  it("drops what another tab dismissed, or everything for null", () => {
    const inbox = storeNotificationInbox();
    inbox.notifications = [notification(1), notification(2)];

    inbox.applyDismissed([1]);
    expect(inbox.notifications.map((n) => n.id)).toEqual([2]);

    inbox.applyDismissed(null);
    expect(inbox.notifications).toEqual([]);
  });

  it("brings a notification back when the server refuses to dismiss it", async () => {
    dismiss.mockRejectedValue(new Error("offline"));
    const inbox = storeNotificationInbox();
    inbox.notifications = [notification(3), notification(2), notification(1)];

    const pending = inbox.dismiss(2);
    expect(inbox.notifications.map((n) => n.id)).toEqual([3, 1]);

    await expect(pending).rejects.toThrow("offline");
    expect(inbox.notifications.map((n) => n.id)).toEqual([3, 2, 1]);
  });

  it("marks rows unread again when the server refuses", async () => {
    markRead.mockRejectedValue(new Error("offline"));
    const inbox = storeNotificationInbox();
    inbox.notifications = [notification(2), notification(1)];

    await expect(inbox.markRead([2, 1])).rejects.toThrow("offline");

    expect(inbox.unreadCount).toBe(2);
  });

  describe("a fetch answered after a change", () => {
    let answer!: (value: unknown) => void;

    beforeEach(() => {
      getNotifications.mockReturnValue(
        new Promise((resolve) => {
          answer = resolve;
        }),
      );
    });

    it("keeps a notification pushed meanwhile", async () => {
      const inbox = storeNotificationInbox();
      const pending = inbox.fetch();

      inbox.receive(notification(3));
      answer({ data: [notification(2), notification(1)] });
      await pending;

      expect(inbox.notifications.map((n) => n.id)).toEqual([3, 2, 1]);
    });

    it("doesn't bring back one dismissed meanwhile", async () => {
      dismiss.mockResolvedValue({});
      const inbox = storeNotificationInbox();
      inbox.notifications = [notification(2), notification(1)];
      const pending = inbox.fetch();

      await inbox.dismiss(2);
      answer({ data: [notification(2), notification(1)] });
      await pending;

      expect(inbox.notifications.map((n) => n.id)).toEqual([1]);
    });

    it("keeps what was read meanwhile", async () => {
      const inbox = storeNotificationInbox();
      const pending = inbox.fetch();

      inbox.applyRead(null);
      answer({ data: [notification(2), notification(1)] });
      await pending;

      expect(inbox.unreadCount).toBe(0);
    });

    it("replays nothing onto a later fetch", async () => {
      const inbox = storeNotificationInbox();
      const first = inbox.fetch();
      inbox.applyDismissed([1]);
      answer({ data: [notification(2)] });
      await first;

      getNotifications.mockResolvedValue({
        data: [notification(2), notification(1)],
      });
      await inbox.fetch();

      expect(inbox.notifications.map((n) => n.id)).toEqual([2, 1]);
    });
  });

  it("sends only the ids it marks read", async () => {
    markRead.mockResolvedValue({});
    const inbox = storeNotificationInbox();
    inbox.notifications = [notification(1), notification(2)];

    await inbox.markRead([1]);

    expect(markRead).toHaveBeenCalledWith([1]);
    expect(inbox.unreadCount).toBe(1);
  });
});
