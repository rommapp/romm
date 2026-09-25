import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { defineComponent } from "vue";
import type { NotificationChannelSchema } from "@/__generated__";
import { makeChannel as channel } from "@/v2/utils/notificationChannels.fixtures";
import NotificationChannelsSection from "./NotificationChannelsSection.vue";

const api = vi.hoisted(() => ({
  getChannels: vi.fn(),
  update: vi.fn(),
  remove: vi.fn(),
  test: vi.fn(),
  confirm: vi.fn(),
  resendCode: vi.fn(),
}));
const snackbar = vi.hoisted(() => ({
  success: vi.fn(),
  error: vi.fn(),
  info: vi.fn(),
}));
const confirmDialog = vi.hoisted(() => vi.fn());

vi.mock("@/services/api/notificationChannel", () => ({ default: api }));
vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));
vi.mock("@/v2/composables/useSnackbar", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/v2/composables/useSnackbar")>()),
  useSnackbar: () => snackbar,
}));
vi.mock("@/v2/composables/useConfirm", () => ({
  useConfirm: () => confirmDialog,
}));

const DialogStub = defineComponent({ emits: ["saved"], template: "<div />" });

async function mountWith(channels: NotificationChannelSchema[]) {
  api.getChannels.mockResolvedValue({ data: channels });
  const wrapper = mount(NotificationChannelsSection, {
    global: { stubs: { NotificationChannelDialog: DialogStub } },
  });
  await flushPromises();
  return wrapper;
}

function button(wrapper: Awaited<ReturnType<typeof mountWith>>, label: string) {
  return wrapper.find(`button[aria-label="${label}"]`);
}

describe("NotificationChannelsSection", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.resetAllMocks();
  });

  it("says there are none yet", async () => {
    const wrapper = await mountWith([]);

    expect(wrapper.text()).toContain("notifications.channels-empty");
  });

  it("lists each channel with its service, filters and last error", async () => {
    const wrapper = await mountWith([
      channel({
        min_level: "warning",
        topics: ["scans", "tasks"],
        last_error: "Failed to send Discord notification: error=404.",
      }),
    ]);

    const text = wrapper.find(".r-v2-channel").text();
    expect(wrapper.find(".r-v2-channel .r-tag").text()).toBe("Discord");
    expect(text).toContain("discord://1...0/a...p/");
    expect(text).toContain(
      "notifications.channel-level-warning · notifications.topic-scans, notifications.topic-tasks",
    );
    expect(text).toContain("notifications.channel-last-error");
  });

  it("says a code went out only for an address new to the channel", async () => {
    const waiting = channel({
      type: "email",
      service: null,
      target: "a@example.com",
      confirmed: false,
    });
    const wrapper = await mountWith([waiting]);
    const dialog = wrapper.findComponent(DialogStub);

    dialog.vm.$emit("saved", { ...waiting, name: "Renamed" });
    expect(snackbar.info).not.toHaveBeenCalled();
    expect(snackbar.success).toHaveBeenCalledWith(
      "notifications.channel-saved",
    );

    dialog.vm.$emit("saved", { ...waiting, target: "b@example.com" });
    expect(snackbar.info).toHaveBeenCalledOnce();
  });

  it("turns a channel off at once and back on if the server refuses", async () => {
    let refuse!: (error: Error) => void;
    api.update.mockReturnValue(
      new Promise((_, reject) => {
        refuse = reject;
      }),
    );
    const wrapper = await mountWith([channel()]);

    await wrapper.find('[role="switch"]').trigger("click");
    expect(wrapper.find(".r-v2-channel").classes()).toContain(
      "r-v2-channel--off",
    );

    vi.spyOn(console, "error").mockImplementation(() => {});
    refuse(new Error("offline"));
    await flushPromises();

    expect(api.update).toHaveBeenCalledWith(1, { enabled: false });
    expect(wrapper.find(".r-v2-channel").classes()).not.toContain(
      "r-v2-channel--off",
    );
    expect(snackbar.error).toHaveBeenCalledOnce();
  });

  it("says whether a test got through", async () => {
    api.test.mockResolvedValue({ data: { ok: false, error: "refused" } });
    const wrapper = await mountWith([channel()]);

    await button(wrapper, "notifications.channel-test").trigger("click");
    await flushPromises();

    expect(api.test).toHaveBeenCalledWith(1);
    expect(snackbar.error).toHaveBeenCalledWith(
      "notifications.channel-test-failed",
    );
    expect(api.getChannels).toHaveBeenCalledTimes(2);
  });

  it("drops a reload that raced a change made meanwhile", async () => {
    const wrapper = await mountWith([channel()]);
    let answer!: (value: { data: NotificationChannelSchema[] }) => void;
    api.getChannels.mockReturnValue(
      new Promise((resolve) => {
        answer = resolve;
      }),
    );
    api.test.mockResolvedValue({ data: { ok: true, error: null } });
    api.update.mockResolvedValue({ data: channel({ enabled: false }) });

    await button(wrapper, "notifications.channel-test").trigger("click");
    await flushPromises();
    await wrapper.find('[role="switch"]').trigger("click");
    await flushPromises();
    answer({ data: [channel()] });
    await flushPromises();

    expect(wrapper.find(".r-v2-channel").classes()).toContain(
      "r-v2-channel--off",
    );
  });

  it("confirms an address with the code typed in", async () => {
    api.confirm.mockResolvedValue({
      data: channel({ type: "email", confirmed: true }),
    });
    const wrapper = await mountWith([
      channel({ type: "email", service: null, confirmed: false }),
    ]);

    await wrapper.find(".r-v2-channel__code input").setValue(" 123456 ");
    await wrapper
      .findAll(".r-v2-channel__code button")
      .find((b) => b.text() === "common.confirm")
      ?.trigger("click");
    await flushPromises();

    expect(api.confirm).toHaveBeenCalledWith(1, "123456");
    expect(wrapper.find(".r-v2-channel__code").exists()).toBe(false);
  });

  it("deletes a channel only once confirmed", async () => {
    confirmDialog.mockResolvedValueOnce(false).mockResolvedValueOnce(true);
    api.remove.mockResolvedValue({});
    const wrapper = await mountWith([channel()]);

    await button(wrapper, "notifications.channel-delete").trigger("click");
    await flushPromises();
    expect(api.remove).not.toHaveBeenCalled();

    await button(wrapper, "notifications.channel-delete").trigger("click");
    await flushPromises();
    expect(api.remove).toHaveBeenCalledWith(1);
    expect(wrapper.find(".r-v2-channel").exists()).toBe(false);
  });

  it("deletes once, holding the button while it does", async () => {
    confirmDialog.mockResolvedValue(true);
    let done!: (value: object) => void;
    api.remove.mockReturnValue(
      new Promise((resolve) => {
        done = resolve;
      }),
    );
    const wrapper = await mountWith([channel()]);

    await button(wrapper, "notifications.channel-delete").trigger("click");
    await flushPromises();
    expect(
      button(wrapper, "notifications.channel-delete").attributes("disabled"),
    ).toBeDefined();
    await button(wrapper, "notifications.channel-delete").trigger("click");
    done({});
    await flushPromises();

    expect(confirmDialog).toHaveBeenCalledOnce();
    expect(api.remove).toHaveBeenCalledOnce();
    expect(wrapper.find(".r-v2-channel").exists()).toBe(false);
  });
});
