import { flushPromises } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { effectScope, type EffectScope } from "vue";
import type { NotificationSchema } from "@/__generated__";
import storeAuth from "@/stores/auth";
import type { User } from "@/stores/users";
import { installNotificationInbox } from "@/v2/composables/useNotificationInbox";
import storeNotificationInbox from "@/v2/stores/notificationInbox";

const { getNotifications, handlers, show } = vi.hoisted(() => ({
  getNotifications: vi.fn(),
  handlers: new Map<string, (payload: unknown) => void>(),
  show: vi.fn(),
}));

vi.mock("@/services/api/notification", () => ({
  default: { getNotifications },
}));

vi.mock("@/v2/composables/useSocketEvent", () => ({
  useSocketEvent: (event: string, handler: (payload: unknown) => void) => {
    handlers.set(event, handler);
    return { stop: () => {} };
  },
}));

vi.mock("@/v2/composables/useSnackbar", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/v2/composables/useSnackbar")>()),
  useSnackbar: () => ({ show }),
}));

function notification(id: number): NotificationSchema {
  return {
    id,
    kind: "custom",
    level: "success",
    title: `Notification ${id}`,
    body: null,
    link: null,
    icon: null,
    data: {},
    actor: null,
    read_at: null,
    created_at: "2026-09-23T10:00:00+00:00",
  };
}

function signIn(id: number) {
  storeAuth().setCurrentUser({ id } as User);
}

function push(event: string, payload: unknown) {
  handlers.get(event)?.(payload);
}

describe("installNotificationInbox", () => {
  let scope: EffectScope;

  beforeEach(() => {
    setActivePinia(createPinia());
    vi.resetAllMocks();
    handlers.clear();
    getNotifications.mockResolvedValue({ data: [] });
    scope = effectScope();
  });

  afterEach(() => {
    scope.stop();
  });

  it("toasts a pushed notification once", async () => {
    signIn(1);
    scope.run(installNotificationInbox);
    await flushPromises();

    push("notifications:new", notification(5));
    push("notifications:new", notification(5));

    expect(storeNotificationInbox().notifications).toHaveLength(1);
    expect(show).toHaveBeenCalledOnce();
    expect(show).toHaveBeenCalledWith("success", "Notification 5", {
      icon: "mdi-check-circle-outline",
    });
  });

  it("leaves the toast to this tab when its own request answered first", async () => {
    signIn(1);
    scope.run(installNotificationInbox);
    await flushPromises();
    storeNotificationInbox().receive(notification(5));

    push("notifications:new", notification(5));

    expect(show).not.toHaveBeenCalled();
  });

  it("applies what another tab read and dismissed", async () => {
    getNotifications.mockResolvedValue({
      data: [notification(2), notification(1)],
    });
    signIn(1);
    scope.run(installNotificationInbox);
    await flushPromises();
    const inbox = storeNotificationInbox();

    push("notifications:read", { ids: [2] });
    push("notifications:dismissed", { ids: [1] });

    expect(inbox.notifications.map((n) => n.id)).toEqual([2]);
    expect(inbox.unreadCount).toBe(0);
  });

  it("drops the last user's inbox even when the next one's can't load", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    getNotifications.mockResolvedValueOnce({ data: [notification(1)] });
    signIn(1);
    scope.run(installNotificationInbox);
    await flushPromises();

    getNotifications.mockRejectedValueOnce(new Error("offline"));
    signIn(2);
    await flushPromises();

    expect(storeNotificationInbox().notifications).toEqual([]);
  });
});
