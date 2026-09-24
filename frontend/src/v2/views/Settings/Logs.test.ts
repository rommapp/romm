/* eslint-disable vue/one-component-per-file */
import { mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { defineComponent, reactive } from "vue";
import storeAuth from "@/stores/auth";
import storeHeartbeat from "@/stores/heartbeat";
import storePermissions from "@/stores/permissions";
import Logs from "./Logs.vue";

const route = reactive<{ query: Record<string, string> }>({ query: {} });

vi.mock("vue-router", async (importOriginal) => ({
  ...(await importOriginal<typeof import("vue-router")>()),
  useRoute: () => route,
  useRouter: () => ({ replace: vi.fn() }),
}));

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

const stub = (name: string) =>
  defineComponent({ name, template: `<div data-testid="${name}" />` });

function render() {
  return mount(Logs, {
    global: {
      stubs: {
        LogViewer: stub("LogViewer"),
        EventLog: stub("EventLog"),
        RTabNav: defineComponent({
          name: "RTabNav",
          props: {
            modelValue: { type: String, default: "" },
            items: { type: Array, default: () => [] },
          },
          template: `<nav :data-active="modelValue" :data-tabs="items.map((i) => i.id).join(',')" />`,
        }),
      },
    },
  });
}

function signIn({
  admin,
  viewer = true,
}: {
  admin: boolean;
  viewer?: boolean;
}) {
  const permissions = storePermissions();
  permissions.isAdmin = admin;
  permissions.hydrated = true;
  storeAuth().setCurrentUser({ oauth_scopes: ["logs.read"] } as never);
  storeHeartbeat().value.FRONTEND.DISABLE_LOGS_VIEWER = !viewer;
}

describe("Logs view", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    route.query = {};
  });

  it("opens an admin on the events, the log a tab away", () => {
    signIn({ admin: true });

    const wrapper = render();

    expect(wrapper.find("nav").attributes("data-tabs")).toBe("events,logs");
    expect(wrapper.find('[data-testid="EventLog"]').exists()).toBe(true);
  });

  it("deep-links to the log", () => {
    signIn({ admin: true });
    route.query = { tab: "logs" };

    const wrapper = render();

    expect(wrapper.find('[data-testid="LogViewer"]').exists()).toBe(true);
  });

  it("keeps the events from anyone else holding logs.read", () => {
    signIn({ admin: false });
    route.query = { tab: "events" };

    const wrapper = render();

    expect(wrapper.find("nav").exists()).toBe(false);
    expect(wrapper.find('[data-testid="LogViewer"]').exists()).toBe(true);
    expect(wrapper.find('[data-testid="EventLog"]').exists()).toBe(false);
  });

  it("leaves an admin the events when the log viewer is off", () => {
    signIn({ admin: true, viewer: false });

    const wrapper = render();

    expect(wrapper.find('[data-testid="LogViewer"]').exists()).toBe(false);
    expect(wrapper.find('[data-testid="EventLog"]').exists()).toBe(true);
  });
});
