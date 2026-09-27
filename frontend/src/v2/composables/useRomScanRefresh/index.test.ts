import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { defineComponent } from "vue";
import { createMemoryHistory, createRouter } from "vue-router";
import { useRomScanRefresh } from "./index";

const handlers = new Map<string, (payload: unknown) => void>();
vi.mock("@/services/socket", () => ({
  default: {
    connected: true,
    connect: vi.fn(),
    on: (event: string, handler: (payload: unknown) => void) => {
      handlers.set(event, handler);
    },
    off: (event: string) => {
      handlers.delete(event);
    },
  },
}));

const { refetchRom } = vi.hoisted(() => ({
  refetchRom: vi.fn(),
}));
vi.mock("@/v2/composables/useRomSync", () => ({
  useRomSync: () => ({ refetchRom }),
}));

async function install(path: string) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: "/", component: { render: () => null } },
      { path: "/rom/:rom", component: { render: () => null } },
    ],
  });
  await router.push(path);
  return mount(
    defineComponent({
      setup() {
        useRomScanRefresh();
        return () => null;
      },
    }),
    { global: { plugins: [router] } },
  );
}

describe("useRomScanRefresh", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    handlers.clear();
    refetchRom.mockClear();
  });

  it("refetches the open rom when a scan finishes", async () => {
    await install("/rom/3");

    handlers.get("scan:done")?.({});
    await flushPromises();

    expect(refetchRom).toHaveBeenCalledWith(3);
  });

  it("does nothing without an open rom", async () => {
    await install("/");

    handlers.get("scan:done")?.({});

    expect(refetchRom).not.toHaveBeenCalled();
  });

  it("does nothing once the view is gone", async () => {
    const wrapper = await install("/rom/3");
    wrapper.unmount();

    handlers.get("scan:done")?.({});
    await flushPromises();

    expect(refetchRom).not.toHaveBeenCalled();
  });
});
