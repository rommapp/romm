import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { defineComponent } from "vue";
import type { DetailedRom } from "@/stores/roms";
import storeRoms from "@/stores/roms";
import { useRomScanRefresh } from "./index";

const handlers = new Map<string, (payload: unknown) => void>();
vi.mock("@/services/socket", () => ({
  default: {
    connected: true,
    connect: vi.fn(),
    on: (event: string, handler: (payload: unknown) => void) => {
      handlers.set(event, handler);
    },
    off: vi.fn(),
  },
}));

const { refetchCurrentRom } = vi.hoisted(() => ({
  refetchCurrentRom: vi.fn(),
}));
vi.mock("@/v2/composables/useRomSync", () => ({
  useRomSync: () => ({ refetchCurrentRom }),
}));

function rom(overrides: Partial<DetailedRom> = {}): DetailedRom {
  return { id: 3, files: [], ...overrides } as DetailedRom;
}

function install() {
  return mount(
    defineComponent({
      setup() {
        useRomScanRefresh();
        return () => null;
      },
    }),
  );
}

describe("useRomScanRefresh", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    handlers.clear();
    refetchCurrentRom.mockClear();
  });

  it("refetches the open rom when a scan finishes", async () => {
    const romsStore = storeRoms();
    romsStore.setCurrentRom(rom());
    install();

    handlers.get("scan:done")?.({});
    await flushPromises();

    expect(refetchCurrentRom).toHaveBeenCalledWith(3);
  });

  it("does nothing without an open rom", () => {
    install();

    handlers.get("scan:done")?.({});

    expect(refetchCurrentRom).not.toHaveBeenCalled();
  });

  it("does nothing once the view is gone", async () => {
    const romsStore = storeRoms();
    romsStore.setCurrentRom(rom());
    const wrapper = install();
    wrapper.unmount();

    handlers.get("scan:done")?.({});
    await flushPromises();

    expect(refetchCurrentRom).not.toHaveBeenCalled();
  });
});
