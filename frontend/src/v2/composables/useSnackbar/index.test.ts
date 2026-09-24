import { flushPromises } from "@vue/test-utils";
import mitt from "mitt";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Events } from "@/types/emitter";
import { useSnackbar } from "@/v2/composables/useSnackbar";
import storeNotificationInbox from "@/v2/stores/notificationInbox";
import { makeNotification } from "@/v2/utils/notifications.fixtures";

const { create, emitter } = vi.hoisted(() => ({
  create: vi.fn(),
  emitter: { current: null as ReturnType<typeof mitt<Events>> | null },
}));

vi.mock("@/services/api/notification", () => ({ default: { create } }));

vi.mock("vue", async (importOriginal) => ({
  ...(await importOriginal<typeof import("vue")>()),
  inject: () => emitter.current,
}));

const stored = makeNotification({
  id: 9,
  level: "success",
  title: "Upload finished",
  link: "/rom/12",
});

describe("useSnackbar persist", () => {
  const shown = vi.fn();

  beforeEach(() => {
    setActivePinia(createPinia());
    vi.resetAllMocks();
    emitter.current = mitt<Events>();
    emitter.current.on("snackbarShow", shown);
  });

  it("keeps the message and shows it once", async () => {
    create.mockResolvedValue({ data: [stored] });

    useSnackbar().success("Upload finished", { persist: { link: "/rom/12" } });
    await flushPromises();

    expect(create).toHaveBeenCalledWith({
      level: "success",
      title: "Upload finished",
      body: undefined,
      link: "/rom/12",
      icon: undefined,
      data: { origin_tab: expect.any(String) },
    });
    expect(storeNotificationInbox().notifications).toEqual([stored]);
    expect(shown).toHaveBeenCalledOnce();
    expect(shown.mock.calls[0][0]).not.toHaveProperty("persist");
  });

  it("shows the toast without waiting for the request", () => {
    create.mockReturnValue(new Promise(() => {}));

    useSnackbar().success("Upload finished", { persist: true, timeout: 6000 });

    expect(shown).toHaveBeenCalledWith({
      msg: "Upload finished",
      color: "success",
      timeout: 6000,
    });
  });

  it("still shows the message when it can't be kept", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    create.mockRejectedValue(new Error("offline"));

    useSnackbar().error("Upload failed", { persist: true });
    await flushPromises();

    expect(shown).toHaveBeenCalledOnce();
  });
});
