import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import MissingGamesSection from "./MissingGamesSection.vue";

const { getRoms } = vi.hoisted(() => ({ getRoms: vi.fn() }));

vi.mock("@/services/api/rom", () => ({ default: { getRoms } }));
vi.mock("@/services/api/task", () => ({ default: { runTask: vi.fn() } }));

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

vi.mock("@/v2/composables/useConfirm", () => ({
  useConfirm: () => vi.fn().mockResolvedValue(false),
}));
vi.mock("@/v2/composables/useSnackbar", () => ({
  useSnackbar: () => ({ success: vi.fn(), error: vi.fn() }),
}));
vi.mock("@/v2/composables/useWebpSupport", () => ({
  useWebpSupport: () => ({ supportsWebp: { value: true } }),
}));

function mountSection() {
  return mount(MissingGamesSection, {
    global: {
      stubs: {
        CachedPlatformIcon: true,
        GameListHeader: true,
        GameListRow: true,
        GameListSkeletonRow: true,
        RBtn: true,
        RIcon: true,
        RMenu: true,
        RMenuItem: true,
        RSelect: true,
        RTag: true,
        RVirtualScroller: true,
      },
    },
  });
}

describe("MissingGamesSection", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    getRoms.mockReset();
    getRoms.mockResolvedValue({
      data: { total: 0, items: [], char_index: {}, rom_id_index: [] },
    });
  });

  // The tab renders no filter drawer, no A-Z strip and drives its scroller
  // off `total` alone, so asking for those sidecars costs three whole-library
  // scans and displays two of them nowhere (issue #3992).
  it("bootstraps without the sidecars it does not render", async () => {
    mountSection();
    await flushPromises();

    expect(getRoms).toHaveBeenCalledTimes(1);
    const params = getRoms.mock.calls[0][0];
    expect(params.filterMissing).toBe(true);
    expect(params.withCharIndex).toBe(false);
    expect(params.withFilterValues).toBe(false);
    expect(params.withRomIdIndex).toBe(false);
  });

  it("keeps the sidecars off when the sort order changes", async () => {
    const wrapper = mountSection();
    await flushPromises();
    getRoms.mockClear();

    wrapper
      .findComponent({ name: "GameListHeader" })
      .vm.$emit("sort", { key: "fs_size_bytes", dir: "desc" });
    await flushPromises();

    const params = getRoms.mock.calls[0][0];
    expect(params.orderBy).toBe("fs_size_bytes");
    expect(params.withCharIndex).toBe(false);
    expect(params.withFilterValues).toBe(false);
    expect(params.withRomIdIndex).toBe(false);
  });
});
