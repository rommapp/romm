import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { nextTick } from "vue";
import type { SimpleRom } from "@/stores/roms";
import { serverError } from "@/test-utils/serverError";
import storeGallerySelection from "@/v2/stores/gallerySelection";
import MissingGamesSection from "./MissingGamesSection.vue";

const { getRoms, runTask, getTaskById, confirm, snackbarError } = vi.hoisted(
  () => ({
    getRoms: vi.fn(),
    runTask: vi.fn(),
    getTaskById: vi.fn(),
    confirm: vi.fn(),
    snackbarError: vi.fn(),
  }),
);

vi.mock("@/services/api/rom", () => ({ default: { getRoms } }));
vi.mock("@/services/api/task", () => ({
  default: { runTask, getTaskById },
}));

vi.mock("vue-i18n", () => ({
  useI18n: () => ({
    t: (key: string, params?: Record<string, unknown>) =>
      params ? `${key}::${JSON.stringify(params)}` : key,
  }),
}));

vi.mock("@/v2/composables/useConfirm", () => ({
  useConfirm: () => confirm,
}));
vi.mock("@/v2/composables/useSnackbar", () => ({
  useSnackbar: () => ({ success: vi.fn(), error: snackbarError }),
}));

// The kebab's items live in RMenu's default slot; the auto-stub drops slot
// content, so render it to reach the cleanup action.
const RMenuStub = {
  name: "RMenu",
  template: '<div><slot name="activator" :props="{}" /><slot /></div>',
};
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
        RMenu: RMenuStub,
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
      data: { total: 1, items: [], char_index: {}, rom_id_index: [] },
    });
    runTask.mockReset();
    runTask.mockResolvedValue({ data: { task_id: "job-1" } });
    getTaskById.mockReset();
    getTaskById.mockResolvedValue({ data: { status: "finished" } });
    confirm.mockReset();
    confirm.mockResolvedValue(false);
    snackbarError.mockReset();
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

  it("tells why the server refused the cleanup", async () => {
    confirm.mockResolvedValue(true);
    runTask.mockRejectedValue(serverError("No task worker is listening"));
    const wrapper = mountSection();
    await flushPromises();

    wrapper.findComponent({ name: "RMenuItem" }).vm.$emit("click");
    await flushPromises();

    expect(snackbarError).toHaveBeenCalledWith(
      'settings.couldnt-queue-cleanup::{"error":"No task worker is listening"}',
    );
  });

  // Rows are selectable here, so the selection needs the same bulk actions
  // it gets in the gallery rather than none at all (issue #4036).
  it("raises the gallery's bulk actions once a row is selected", async () => {
    const wrapper = mountSection();
    await flushPromises();
    const bar = wrapper.findComponent({ name: "SelectionBar" });
    expect(bar.classes()).not.toContain("selection-bar--visible");

    storeGallerySelection().toggle({ id: 1, name: "Game 1" } as SimpleRom, 0);
    await nextTick();

    expect(bar.classes()).toContain("selection-bar--visible");
  });

  // These rows point at files that are gone, so a download can only 404.
  it("keeps download off the bar", async () => {
    const wrapper = mountSection();
    await flushPromises();

    expect(
      wrapper.findComponent({ name: "SelectionBar" }).props("hideDownload"),
    ).toBe(true);
  });
});
