import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { nextTick, ref } from "vue";
import PdfViewer from "./PdfViewer.vue";

vi.mock("vue-i18n");
vi.mock("vue3-pdf-app", () => ({
  default: {
    name: "VuePdfApp",
    props: { pageScale: String },
    emits: ["pages-rendered"],
    template: `<div class="pdf-app-stub" :data-scale="pageScale" />`,
  },
}));
vi.mock("@/composables/useReadingProgress", () => ({
  useReadingProgress: () => ({
    progress: ref(0),
    restore: vi.fn(() => Promise.resolve({ lastPage: null })),
    setPage: vi.fn(),
    suppressWhileRestoring: vi.fn(),
  }),
}));

type ResizeCallback = (entries: { contentRect: { width: number } }[]) => void;
let resize: ResizeCallback | undefined;

beforeEach(() => {
  localStorage.clear();
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

type Handler = (payload: {
  scale: number;
  pageNumber: number;
  presetValue?: string | undefined;
}) => void;

// Stands in for pdf.js: a preset resolves to a fixed fitted scale, and every
// scale change is announced the way pdf.js does, synchronously.
function fakePdfApp(initialFit: number) {
  let fittedScale = initialFit;
  const handlers: Record<string, Handler[]> = {};
  const emit = (event: string, scale: number, presetValue?: string) =>
    handlers[event]?.forEach((h) => h({ scale, pageNumber: 1, presetValue }));
  let scale = 1;
  let scaleValue = "";
  const pdfViewer = {
    get currentScale() {
      return scale;
    },
    set currentScale(value: number) {
      scale = value;
      scaleValue = String(value);
      emit("scalechanging", value);
    },
    get currentScaleValue() {
      return scaleValue;
    },
    set currentScaleValue(value: string) {
      scaleValue = value;
      scale = fittedScale;
      emit("scalechanging", fittedScale, value);
    },
  };
  return {
    app: {
      page: 1,
      pagesCount: 4,
      pdfViewer,
      eventBus: {
        on: (event: string, handler: Handler) => {
          (handlers[event] ??= []).push(handler);
        },
      },
    },
    pdfViewer,
    zoomFromPdf: (value: number) => {
      scale = value;
      emit("scalechanging", value);
    },
    refitFromPdf: (value: number) => {
      fittedScale = value;
      scale = value;
      emit("scalechanging", value, scaleValue);
    },
  };
}

describe("PdfViewer zoom", () => {
  async function mountLoaded(fittedScale: number) {
    const wrapper = mount(PdfViewer, {
      props: { pdfUrl: "/manual.pdf" },
      global: { stubs: { RTooltip: true, RProgressLinear: true } },
    });
    resize?.([{ contentRect: { width: 640 } }]);
    await nextTick();
    const pdf = fakePdfApp(fittedScale);
    wrapper
      .findComponent({ name: "VuePdfApp" })
      .vm.$emit("pages-rendered", pdf.app);
    await flushPromises();
    return { wrapper, pdf };
  }

  it("opens fitted to the width and zooms over the fitted scale", async () => {
    const { wrapper, pdf } = await mountLoaded(2);

    expect(wrapper.find(".pdf-app-stub").attributes("data-scale")).toBe(
      "page-width",
    );
    expect(pdf.pdfViewer.currentScaleValue).toBe("page-width");

    await wrapper.find('[aria-label="common.zoom-in"]').trigger("click");
    await flushPromises();

    expect(pdf.pdfViewer.currentScale).toBe(2.5);
    expect(wrapper.find(".r-zoom__level").text()).toBe("125%");
  });

  it("switches to fitting the page", async () => {
    const { wrapper, pdf } = await mountLoaded(2);

    await wrapper.find('[aria-label="rom.fit-page"]').trigger("click");
    await flushPromises();

    expect(pdf.pdfViewer.currentScaleValue).toBe("page-fit");
    expect(wrapper.find(".r-zoom__level").text()).toBe("100%");
  });

  it("follows a zoom pdf.js made on its own without applying it back", async () => {
    const { wrapper, pdf } = await mountLoaded(2);

    pdf.zoomFromPdf(3);
    await flushPromises();

    expect(wrapper.find(".r-zoom__level").text()).toBe("150%");
    expect(pdf.pdfViewer.currentScale).toBe(3);
    expect(pdf.pdfViewer.currentScaleValue).toBe("page-width");
  });

  it("keeps 100% when pdf.js refits the page to a resized pane", async () => {
    const { wrapper, pdf } = await mountLoaded(2);

    pdf.refitFromPdf(1.6);
    await flushPromises();
    expect(wrapper.find(".r-zoom__level").text()).toBe("100%");

    await wrapper.find('[aria-label="common.zoom-in"]').trigger("click");
    await flushPromises();
    expect(pdf.pdfViewer.currentScale).toBe(2);
  });
});
