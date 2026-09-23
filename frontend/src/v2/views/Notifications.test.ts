/* eslint-disable vue/one-component-per-file */
import { mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { defineComponent, reactive } from "vue";
import storePermissions from "@/stores/permissions";
import Notifications from "./Notifications.vue";

const { replace } = vi.hoisted(() => ({ replace: vi.fn() }));
const route = reactive<{ query: Record<string, string> }>({ query: {} });

vi.mock("vue-router", async (importOriginal) => ({
  ...(await importOriginal<typeof import("vue-router")>()),
  useRoute: () => route,
  useRouter: () => ({ replace }),
}));

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

const stub = (name: string) =>
  defineComponent({ name, template: `<div data-testid="${name}" />` });

function render() {
  return mount(Notifications, {
    global: {
      stubs: {
        NotificationInbox: stub("NotificationInbox"),
        NotificationChannelsSection: stub("NotificationChannelsSection"),
        SendNotificationSection: stub("SendNotificationSection"),
        RTabNav: defineComponent({
          name: "RTabNav",
          props: {
            modelValue: { type: String, default: "" },
            items: { type: Array, default: () => [] },
          },
          emits: ["update:modelValue"],
          template: `<nav :data-active="modelValue" :data-tabs="items.map((i) => i.id).join(',')" />`,
        }),
      },
    },
  });
}

function signIn(isAdmin: boolean) {
  const permissions = storePermissions();
  permissions.isAdmin = isAdmin;
  permissions.hydrated = true;
}

describe("Notifications view", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    route.query = {};
    replace.mockClear();
  });

  it("gives a user the inbox and their channels, never the form", () => {
    signIn(false);
    route.query = { tab: "send" };

    const wrapper = render();

    expect(wrapper.find("nav").attributes("data-tabs")).toBe("inbox,channels");
    expect(wrapper.find('[data-testid="NotificationInbox"]').exists()).toBe(
      true,
    );
    expect(
      wrapper.find('[data-testid="SendNotificationSection"]').exists(),
    ).toBe(false);
  });

  it("gives an admin a send tab too", () => {
    signIn(true);

    const wrapper = render();

    expect(wrapper.find("nav").attributes("data-tabs")).toBe(
      "inbox,channels,send",
    );
    expect(wrapper.find("nav").attributes("data-active")).toBe("inbox");
  });

  it("deep-links anyone to their channels", () => {
    signIn(false);
    route.query = { tab: "channels" };

    const wrapper = render();

    expect(wrapper.find("nav").attributes("data-active")).toBe("channels");
    expect(
      wrapper.find('[data-testid="NotificationChannelsSection"]').exists(),
    ).toBe(true);
    expect(wrapper.find('[data-testid="NotificationInbox"]').exists()).toBe(
      false,
    );
  });

  it("deep-links an admin to the form", () => {
    signIn(true);
    route.query = { tab: "send" };

    const wrapper = render();

    expect(wrapper.find("nav").attributes("data-active")).toBe("send");
    expect(
      wrapper.find('[data-testid="SendNotificationSection"]').exists(),
    ).toBe(true);
    expect(wrapper.find('[data-testid="NotificationInbox"]').exists()).toBe(
      false,
    );
  });

  it("keeps the inbox unmounted while it can't tell who follows a form link", () => {
    route.query = { tab: "send" };

    const wrapper = render();

    expect(wrapper.find('[data-testid="NotificationInbox"]').exists()).toBe(
      false,
    );
  });

  it("puts the chosen tab in the URL", async () => {
    signIn(true);
    const wrapper = render();

    await wrapper
      .findComponent({ name: "RTabNav" })
      .vm.$emit("update:modelValue", "send");
    expect(replace).toHaveBeenLastCalledWith({ query: { tab: "send" } });

    await wrapper
      .findComponent({ name: "RTabNav" })
      .vm.$emit("update:modelValue", "inbox");
    expect(replace).toHaveBeenLastCalledWith({ query: { tab: undefined } });
  });
});
