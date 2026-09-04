import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { defineComponent } from "vue";
import type { RomFileSchema } from "@/__generated__";
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

const { getRom, syncCachedRom } = vi.hoisted(() => ({
  getRom: vi.fn(),
  syncCachedRom: vi.fn(),
}));
vi.mock("@/services/api/rom", () => ({ default: { getRom } }));
vi.mock("@/v2/composables/useRomSync", () => ({
  useRomSync: () => ({ syncCachedRom }),
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
    getRom.mockReset();
    syncCachedRom.mockClear();
  });

  it("refetches the open rom when a scan finishes", async () => {
    const romsStore = storeRoms();
    romsStore.setCurrentRom(rom());
    const fresh = rom({ files: [{ id: 9 } as RomFileSchema] });
    getRom.mockResolvedValue({ data: fresh });
    install();

    handlers.get("scan:done")?.({});
    await flushPromises();

    expect(getRom).toHaveBeenCalledWith({ romId: 3 });
    expect(romsStore.currentRom).toStrictEqual(fresh);
    expect(syncCachedRom).toHaveBeenCalledWith(fresh);
  });

  it("drops a response for a rom the user already left", async () => {
    const romsStore = storeRoms();
    romsStore.setCurrentRom(rom());
    let resolve: (value: unknown) => void = () => {};
    getRom.mockReturnValue(new Promise((r) => (resolve = r)));
    install();

    handlers.get("scan:done")?.({});
    romsStore.setCurrentRom(rom({ id: 4 }));
    resolve({ data: { id: 3 } });
    await flushPromises();

    expect(romsStore.currentRom?.id).toBe(4);
    expect(syncCachedRom).not.toHaveBeenCalled();
  });

  it("does nothing without an open rom", () => {
    install();

    handlers.get("scan:done")?.({});

    expect(getRom).not.toHaveBeenCalled();
  });
});
