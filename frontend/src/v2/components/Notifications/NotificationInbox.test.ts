/* eslint-disable vue/one-component-per-file */
import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { defineComponent } from "vue";
import type { NotificationSchema } from "@/__generated__";
import storeNotificationInbox from "@/v2/stores/notificationInbox";
import { makeNotification } from "@/v2/utils/notifications.fixtures";
import NotificationInbox from "./NotificationInbox.vue";

const { api, confirm } = vi.hoisted(() => ({
  api: {
    dismiss: vi.fn(),
    dismissAll: vi.fn(),
    getNotifications: vi.fn(),
    markRead: vi.fn(),
  },
  confirm: vi.fn(),
}));

vi.mock("@/services/api/notification", () => ({ default: api }));

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

vi.mock("@/v2/utils/notifications", () => ({
  describeNotification: (n: NotificationSchema) => ({
    icon: "mdi-bell-outline",
    title: `title-${n.id}`,
    body: null,
    to: null,
    toast: true,
  }),
}));

vi.mock("@/v2/composables/useConfirm", () => ({
  useConfirm: () => confirm,
}));

vi.mock("@/v2/composables/useGridNav", () => ({ useGridNav: () => {} }));

vi.mock("@/v2/composables/useSnackbar", () => ({
  useSnackbar: () => ({ error: vi.fn() }),
}));

vi.mock("@/v2/components/shared/AssetTimestamp.vue", () => ({
  default: defineComponent({ template: "<span />" }),
}));

vi.mock("@v2/lib", () => ({
  RAvatar: defineComponent({ template: "<span />" }),
  RBtn: defineComponent({
    emits: ["click"],
    template: "<button @click=\"$emit('click')\"><slot /></button>",
  }),
  REmptyState: defineComponent({
    props: { title: { type: String, default: "" } },
    template: '<div class="empty-state">{{ title }}</div>',
  }),
  RIcon: defineComponent({ template: "<i />" }),
  RSkeletonBlock: defineComponent({ template: "<div />" }),
}));

function notification(
  id: number,
  overrides: Partial<NotificationSchema> = {},
): NotificationSchema {
  return makeNotification({ id, kind: "role_changed", ...overrides });
}

function mountWith(notifications: NotificationSchema[]) {
  const inbox = storeNotificationInbox();
  inbox.notifications = notifications;
  inbox.loaded = true;
  return { inbox, wrapper: mount(NotificationInbox) };
}

describe("NotificationInbox", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.resetAllMocks();
    api.markRead.mockResolvedValue({});
    api.dismiss.mockResolvedValue({});
    api.dismissAll.mockResolvedValue({});
  });

  it("marks what it shows read and keeps their accent for the visit", async () => {
    const { inbox, wrapper } = mountWith([
      notification(2),
      notification(1, { read_at: "2026-09-22T10:00:00+00:00" }),
    ]);
    await flushPromises();

    expect(api.markRead).toHaveBeenCalledWith([2]);
    expect(inbox.unreadCount).toBe(0);
    const rows = wrapper.findAll(".r-v2-notification");
    expect(rows[0].classes()).toContain("r-v2-notification--unread");
    expect(rows[1].classes()).not.toContain("r-v2-notification--unread");
  });

  it("tries a refused mark once a visit rather than in a loop", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    api.markRead.mockRejectedValue(new Error("offline"));
    const { inbox } = mountWith([notification(2)]);
    await flushPromises();

    expect(api.markRead).toHaveBeenCalledOnce();
    expect(inbox.unreadCount).toBe(1);
  });

  it("dismisses one row for good", async () => {
    const { wrapper } = mountWith([notification(2), notification(1)]);

    await wrapper.findAll(".r-v2-notification button")[0].trigger("click");
    await flushPromises();

    expect(api.dismiss).toHaveBeenCalledWith(2);
    expect(wrapper.findAll(".r-v2-notification")).toHaveLength(1);
  });

  it("clears everything only once confirmed", async () => {
    confirm.mockResolvedValueOnce(false).mockResolvedValueOnce(true);
    const { wrapper } = mountWith([notification(2), notification(1)]);
    const dismissAll = wrapper.find(".r-v2-notifications__head button");

    await dismissAll.trigger("click");
    await flushPromises();
    expect(api.dismissAll).not.toHaveBeenCalled();

    await dismissAll.trigger("click");
    await flushPromises();
    expect(api.dismissAll).toHaveBeenCalledOnce();
    expect(wrapper.find(".empty-state").exists()).toBe(true);
  });
});
