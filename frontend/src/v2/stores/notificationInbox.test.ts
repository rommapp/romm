import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { NotificationSchema } from "@/__generated__";
import storeNotificationInbox from "@/v2/stores/notificationInbox";

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
  return {
    id,
    kind: "task_completed",
    level: "success",
    title: null,
    body: null,
    link: null,
    icon: null,
    data: {},
    actor: null,
    read_at: null,
    created_at: "2026-09-23T10:00:00+00:00",
    ...overrides,
  };
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

  it("sends a notification to the signed-in user", async () => {
    create.mockResolvedValue({ data: [notification(5)] });
    const inbox = storeNotificationInbox();

    const sent = await inbox.send({ title: "Sync finished", level: "success" });

    expect(create).toHaveBeenCalledWith({
      title: "Sync finished",
      level: "success",
    });
    expect(sent.id).toBe(5);
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
    inbox.notifications = [notification(1), notification(2)];

    const pending = inbox.dismiss(1);
    expect(inbox.notifications.map((n) => n.id)).toEqual([2]);

    await expect(pending).rejects.toThrow("offline");
    expect(inbox.notifications.map((n) => n.id)).toEqual([1, 2]);
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
