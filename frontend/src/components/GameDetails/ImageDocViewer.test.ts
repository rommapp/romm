import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ref } from "vue";
import ImageDocViewer from "./ImageDocViewer.vue";

vi.mock("vue-i18n");

const progress = vi.hoisted(() => ({
  restore: vi.fn(),
  setPage: vi.fn(),
  suppressWhileRestoring: vi.fn(),
}));
vi.mock("@/composables/useReadingProgress", () => ({
  useReadingProgress: () => ({ progress: ref(0), ...progress }),
}));

const getImageDocPageCount = vi.hoisted(() => vi.fn());
vi.mock("@/services/api/rom", () => ({
  default: { getImageDocPageCount },
}));

function mountViewer() {
  return mount(ImageDocViewer, {
    props: {
      pagesPath: "/roms/1/files/5/pages",
      version: "v1",
      downloadUrl: "/api/roms/5/files/content/issue.cbz",
      fileName: "issue.cbz",
      romId: 1,
      fileId: 5,
    },
    global: { stubs: { RTooltip: true, RProgressLinear: true } },
  });
}

function pageSrc(wrapper: ReturnType<typeof mountViewer>): string {
  return wrapper.find(".r-imgdoc__img").attributes("src") ?? "";
}

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  getImageDocPageCount.mockResolvedValue({ data: { count: 3 } });
  progress.restore.mockResolvedValue({ progress: 0, lastPage: null });
});

describe("ImageDocViewer", () => {
  it("opens on the first page and records it", async () => {
    const wrapper = mountViewer();
    await flushPromises();

    expect(getImageDocPageCount).toHaveBeenCalledWith({
      pagesPath: "/roms/1/files/5/pages",
    });
    expect(pageSrc(wrapper)).toBe("/api/roms/1/files/5/pages/1?v=v1");
    expect(progress.setPage).toHaveBeenCalledWith(1, 3);
  });

  it("restores the saved page without recording it again", async () => {
    progress.restore.mockResolvedValue({ progress: 0.66, lastPage: 2 });

    const wrapper = mountViewer();
    await flushPromises();

    expect(pageSrc(wrapper)).toBe("/api/roms/1/files/5/pages/2?v=v1");
    expect(progress.suppressWhileRestoring).toHaveBeenCalled();
    expect(progress.setPage).not.toHaveBeenCalled();
  });

  it("turns pages with the arrow keys and leaves the key unclaimed at the end", async () => {
    const wrapper = mountViewer();
    await flushPromises();
    const next = wrapper.find(".r-imgdoc__turn--next");

    await next.trigger("keydown", { key: "ArrowRight" });
    expect(pageSrc(wrapper)).toBe("/api/roms/1/files/5/pages/2?v=v1");
    expect(progress.setPage).toHaveBeenLastCalledWith(2, 3);

    await next.trigger("keydown", { key: "End" });
    expect(pageSrc(wrapper)).toBe("/api/roms/1/files/5/pages/3?v=v1");

    const atEnd = new KeyboardEvent("keydown", {
      key: "ArrowRight",
      cancelable: true,
    });
    next.element.dispatchEvent(atEnd);
    expect(atEnd.defaultPrevented).toBe(false);
  });

  it("keeps the turn zones focusable at either end so the keys still work", async () => {
    const wrapper = mountViewer();
    await flushPromises();
    const prev = wrapper.find(".r-imgdoc__turn--prev");
    const next = wrapper.find(".r-imgdoc__turn--next");

    expect(prev.attributes("disabled")).toBeUndefined();
    expect(prev.attributes("aria-disabled")).toBe("true");

    await next.trigger("keydown", { key: "End" });
    expect(next.attributes("disabled")).toBeUndefined();
    expect(next.attributes("aria-disabled")).toBe("true");

    await next.trigger("keydown", { key: "ArrowLeft" });
    expect(pageSrc(wrapper)).toBe("/api/roms/1/files/5/pages/2?v=v1");
    expect(next.attributes("aria-disabled")).toBe("false");
  });

  it("turns back by clicking the left half of the page", async () => {
    progress.restore.mockResolvedValue({ progress: 0.66, lastPage: 2 });
    const wrapper = mountViewer();
    await flushPromises();

    await wrapper.find(".r-imgdoc__turn--prev").trigger("click");

    expect(pageSrc(wrapper)).toBe("/api/roms/1/files/5/pages/1?v=v1");
  });

  it("zooms in steps up to a limit and back to the fit when the fit changes", async () => {
    const wrapper = mountViewer();
    await flushPromises();
    const stage = () => wrapper.find(".r-imgdoc__stage");
    const zoomLabel = () => wrapper.find(".r-zoom__level").text();
    const zoomIn = wrapper.find('[aria-label="common.zoom-in"]');

    expect(zoomLabel()).toBe("100%");
    await zoomIn.trigger("click");
    await flushPromises();
    expect(zoomLabel()).toBe("125%");
    expect(stage().attributes("style")).toContain("--r-imgdoc-zoom: 1.25");

    for (let i = 0; i < 10; i++) await zoomIn.trigger("click");
    await flushPromises();
    expect(zoomLabel()).toBe("400%");
    expect(zoomIn.attributes("disabled")).toBeDefined();

    await wrapper.find('[aria-label="rom.fit-width"]').trigger("click");
    await flushPromises();
    expect(zoomLabel()).toBe("100%");
    expect(stage().classes()).toContain("r-imgdoc__stage--width");
  });

  it("zooms out with the minus key on the page", async () => {
    const wrapper = mountViewer();
    await flushPromises();

    await wrapper
      .find(".r-imgdoc__turn--next")
      .trigger("keydown", { key: "-" });
    await flushPromises();

    expect(wrapper.find(".r-zoom__level").text()).toBe("75%");
  });

  it("shows an empty state for an archive without pages", async () => {
    getImageDocPageCount.mockResolvedValue({ data: { count: 0 } });

    const wrapper = mountViewer();
    await flushPromises();

    expect(wrapper.find(".r-imgdoc__img").exists()).toBe(false);
    expect(wrapper.text()).toContain("rom.image-doc-no-pages");
  });
});
