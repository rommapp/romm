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

const { getRom, syncCachedRom } = vi.hoisted(() => ({
  getRom: vi.fn(),
  syncCachedRom: vi.fn(),
}));
vi.mock("@/services/api/rom", () => ({ default: { getRom } }));
vi.mock("@/v2/composables/useRomSync", () => ({
  useRomSync: () => ({ syncCachedRom }),
}));

function install(getRomId: () => number | null) {
  return mount(
    defineComponent({
      setup() {
        useRomScanRefresh(getRomId);
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
    romsStore.setCurrentRom({ id: 3, files: [] } as unknown as DetailedRom);
    const fresh = { id: 3, files: [{ id: 9 }] } as unknown as DetailedRom;
    getRom.mockResolvedValue({ data: fresh });
    install(() => 3);

    handlers.get("scan:done")?.({});
    await flushPromises();

    expect(getRom).toHaveBeenCalledWith({ romId: 3 });
    expect(romsStore.currentRom).toStrictEqual(fresh);
    expect(syncCachedRom).toHaveBeenCalledWith(fresh);
  });

  it("drops a response for a rom the user already left", async () => {
    const romsStore = storeRoms();
    romsStore.setCurrentRom({ id: 3 } as unknown as DetailedRom);
    let resolve: (value: unknown) => void = () => {};
    getRom.mockReturnValue(new Promise((r) => (resolve = r)));
    install(() => 3);

    handlers.get("scan:done")?.({});
    romsStore.setCurrentRom({ id: 4 } as unknown as DetailedRom);
    resolve({ data: { id: 3 } });
    await flushPromises();

    expect(romsStore.currentRom?.id).toBe(4);
    expect(syncCachedRom).not.toHaveBeenCalled();
  });

  it("does nothing without an open rom", () => {
    install(() => null);

    handlers.get("scan:done")?.({});

    expect(getRom).not.toHaveBeenCalled();
  });
});
