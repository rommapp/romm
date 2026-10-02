import { mount } from "@vue/test-utils";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { nextTick, ref } from "vue";
import PdfViewer from "./PdfViewer.vue";

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));
vi.mock("vue3-pdf-app", () => ({
  default: { name: "VuePdfApp", template: `<div class="pdf-app-stub" />` },
}));
vi.mock("@/v2/composables/useReadingProgress", () => ({
  useReadingProgress: () => ({
    progress: ref(0),
    restore: vi.fn(async () => ({ lastPage: null })),
    setPage: vi.fn(),
    suppressWhileRestoring: vi.fn(),
  }),
}));

type ResizeCallback = (entries: { contentRect: { width: number } }[]) => void;
let resize: ResizeCallback | undefined;

beforeEach(() => {
  resize = undefined;
  vi.stubGlobal(
    "ResizeObserver",
    class {
      constructor(callback: ResizeCallback) {
        resize = callback;
      }
      observe() {}
      unobserve() {}
      disconnect() {}
    },
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("PdfViewer", () => {
  it("waits for a laid-out container before loading pdf.js", async () => {
    const wrapper = mount(PdfViewer, {
      props: { pdfUrl: "/manual.pdf" },
      global: { stubs: { RTooltip: true, RIcon: true, RProgressLinear: true } },
    });
    await nextTick();
    expect(wrapper.find(".pdf-app-stub").exists()).toBe(false);

    resize?.([{ contentRect: { width: 0 } }]);
    await nextTick();
    expect(wrapper.find(".pdf-app-stub").exists()).toBe(false);

    resize?.([{ contentRect: { width: 640 } }]);
    await nextTick();
    expect(wrapper.find(".pdf-app-stub").exists()).toBe(true);

    resize?.([{ contentRect: { width: 0 } }]);
    await nextTick();
    expect(wrapper.find(".pdf-app-stub").exists()).toBe(true);
  });
});
