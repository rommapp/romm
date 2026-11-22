import { mount } from "@vue/test-utils";
import { afterAll, beforeAll, describe, expect, it, vi } from "vitest";
import { nextTick } from "vue";
import { stubResizeObserver } from "@/test-utils/resizeObserver";
import RVirtualScroller from "./RVirtualScroller.vue";

const ROW_H = 100;
const VIEWPORT_H = 500;

// happy-dom lays nothing out, so the scroller would measure a 0-high viewport
// and render no rows at all.
const clientHeight = Object.getOwnPropertyDescriptor(
  HTMLElement.prototype,
  "clientHeight",
);
beforeAll(() => {
  Object.defineProperty(HTMLElement.prototype, "clientHeight", {
    configurable: true,
    get: () => VIEWPORT_H,
  });
});
afterAll(() => {
  if (clientHeight) {
    Object.defineProperty(HTMLElement.prototype, "clientHeight", clientHeight);
  }
});
const items = Array.from({ length: 5 }, (_, id) => ({ id }));

async function mountScroller(offsetShift?: { fromIndex: number; px: number }) {
  const wrapper = mount(RVirtualScroller, {
    attachTo: document.body,
    props: {
      items,
      getItemHeight: () => ROW_H,
      height: VIEWPORT_H,
      offsetShift,
    },
    slots: { default: `<div class="row" />` },
  });
  // The viewport is measured on mount, so the first render has no rows yet.
  await nextTick();
  return wrapper;
}

type Scroller = Awaited<ReturnType<typeof mountScroller>>;

/** Each rendered row's y, read off the transform the scroller writes. */
function tops(wrapper: Scroller): number[] {
  return wrapper.findAll(".r-virtual-scroller__item").map((el) => {
    const match = /translateY\((-?[\d.]+)px\)/.exec(
      el.attributes("style") ?? "",
    );
    return Number(match?.[1]);
  });
}

function innerHeight(wrapper: Scroller): number {
  const style = wrapper.get(".r-virtual-scroller__inner").attributes("style");
  return Number(/height:\s*(-?[\d.]+)px/.exec(style ?? "")?.[1]);
}

describe("RVirtualScroller offsetShift", () => {
  it("stacks the rows on their own heights without one", async () => {
    const wrapper = await mountScroller();

    expect(tops(wrapper)).toEqual([0, 100, 200, 300, 400]);
    expect(innerHeight(wrapper)).toBe(500);
    wrapper.unmount();
  });

  // A row animating towards a height the table already reserves: everything
  // after it is pulled back by what it has yet to paint, and the content
  // shrinks to match, so nothing below the row jumps when it settles.
  it("pulls back only the rows after `fromIndex`", async () => {
    const wrapper = await mountScroller({ fromIndex: 1, px: -40 });

    expect(tops(wrapper)).toEqual([0, 100, 160, 260, 360]);
    expect(innerHeight(wrapper)).toBe(460);
    wrapper.unmount();
  });

  it("leaves the rows alone once the shift is back to zero", async () => {
    const wrapper = await mountScroller({ fromIndex: 1, px: 0 });

    expect(tops(wrapper)).toEqual([0, 100, 200, 300, 400]);
    expect(innerHeight(wrapper)).toBe(500);
    wrapper.unmount();
  });
});

describe("RVirtualScroller body", () => {
  it("wraps the head and the rows, but not the prepend, in bodyAttrs", async () => {
    const wrapper = mount(RVirtualScroller, {
      attachTo: document.body,
      props: {
        items,
        getItemHeight: () => ROW_H,
        height: VIEWPORT_H,
        bodyAttrs: { role: "grid", "aria-rowcount": 6 },
      },
      slots: {
        prepend: `<div class="toolbar" />`,
        head: `<div class="header-row" />`,
        default: `<div class="row" />`,
      },
    });
    await nextTick();

    const body = wrapper.get("[role=grid]");
    expect(body.attributes("aria-rowcount")).toBe("6");
    expect(body.find(".header-row").exists()).toBe(true);
    expect(body.findAll(".row")).toHaveLength(items.length);
    expect(body.find(".toolbar").exists()).toBe(false);
    wrapper.unmount();
  });
});

describe("RVirtualScroller resize", () => {
  const many = Array.from({ length: 50 }, (_, id) => ({ id }));

  async function mountObserved() {
    const ro = stubResizeObserver();
    const wrapper = mount(RVirtualScroller, {
      attachTo: document.body,
      props: {
        items: many,
        getItemHeight: () => ROW_H,
        height: VIEWPORT_H,
        overscan: 0,
      },
      slots: {
        prepend: `<div class="toolbar" />`,
        default: `<div class="row" />`,
      },
    });
    await nextTick();
    return { ro, wrapper };
  }

  function lastRange(
    wrapper: Awaited<ReturnType<typeof mountObserved>>["wrapper"],
  ) {
    return wrapper.emitted("update:viewportRange")?.at(-1)?.[0];
  }

  it("re-measures the viewport when the container resizes", async () => {
    const { ro, wrapper } = await mountObserved();
    expect(wrapper.findAll(".row")).toHaveLength(5);

    Object.defineProperty(wrapper.element, "clientHeight", { value: 200 });
    ro.resize(wrapper.element, 0, 200);
    await nextTick();

    expect(wrapper.findAll(".row")).toHaveLength(2);
    wrapper.unmount();
  });

  it("re-reads the inner offset when a band above it resizes", async () => {
    const { ro, wrapper } = await mountObserved();
    const inner = wrapper.get(".r-virtual-scroller__inner").element;
    wrapper.element.scrollTop = 300;
    await wrapper.trigger("scroll");
    expect(lastRange(wrapper)).toEqual({ first: 3, last: 7 });

    Object.defineProperty(inner, "offsetTop", { value: 300 });
    ro.resize(wrapper.get(".r-virtual-scroller__prepend").element, 0, 300);
    await nextTick();

    expect(lastRange(wrapper)).toEqual({ first: 0, last: 4 });
    wrapper.unmount();
  });

  it("stops observing on unmount", async () => {
    const { ro, wrapper } = await mountObserved();
    const container = wrapper.element;
    const band = wrapper.get(".r-virtual-scroller__prepend").element;
    expect(ro.isObserved(container)).toBe(true);
    expect(ro.isObserved(band)).toBe(true);

    wrapper.unmount();

    expect(ro.isObserved(container)).toBe(false);
    expect(ro.isObserved(band)).toBe(false);
  });
});

describe("RVirtualScroller scrollTo", () => {
  it("updates the exposed offset without waiting for a scroll event", async () => {
    const wrapper = await mountScroller();
    wrapper.element.scrollTop = 300;
    wrapper.element.dispatchEvent(new Event("scroll"));
    expect(wrapper.vm.scrollTop).toBe(300);

    wrapper.vm.scrollTo(0);

    expect(wrapper.element.scrollTop).toBe(0);
    expect(wrapper.vm.scrollTop).toBe(0);
    wrapper.unmount();
  });
});

describe("RVirtualScroller pageScroll", () => {
  const many = Array.from({ length: 50 }, (_, id) => ({ id }));
  let pageY = 0;

  function setPageScroll(top: number) {
    pageY = top;
    Object.defineProperty(window, "scrollY", {
      configurable: true,
      get: () => pageY,
    });
  }

  async function mountPage() {
    setPageScroll(0);
    Object.defineProperty(window, "innerHeight", {
      configurable: true,
      value: VIEWPORT_H,
    });
    const wrapper = mount(RVirtualScroller, {
      attachTo: document.body,
      props: {
        items: many,
        getItemHeight: () => ROW_H,
        overscan: 0,
        pageScroll: true,
      },
      slots: { default: `<div class="row" />` },
    });
    await nextTick();
    return wrapper;
  }

  it("windows the rows on the document's scroll", async () => {
    const wrapper = await mountPage();
    expect(tops(wrapper)).toEqual([0, 100, 200, 300, 400]);

    setPageScroll(2000);
    window.dispatchEvent(new Event("scroll"));
    await nextTick();

    expect(wrapper.vm.scrollTop).toBe(2000);
    expect(tops(wrapper)[0]).toBe(2000);
    wrapper.unmount();
  });

  it("lets the list take its full height instead of scrolling itself", async () => {
    const wrapper = await mountPage();
    const style = wrapper.attributes("style") ?? "";
    expect(style).toContain("overflow: visible");
    expect(style).not.toContain("height");
    wrapper.unmount();
  });

  it("tracks how far down the page the list starts", async () => {
    const ro = stubResizeObserver();
    const wrapper = await mountPage();
    const inner = wrapper.get(".r-virtual-scroller__inner").element;
    // The list's page offset: whatever sits above it in the document.
    let above = 0;
    vi.spyOn(inner, "getBoundingClientRect").mockImplementation(
      () => ({ top: above - window.scrollY }) as DOMRect,
    );

    above = 1000;
    ro.resize(document.body, 0, 6000);
    setPageScroll(1300);
    window.dispatchEvent(new Event("scroll"));
    await nextTick();
    expect(tops(wrapper)[0]).toBe(300);

    const scrollTo = vi.spyOn(window, "scrollTo").mockImplementation(() => {});
    wrapper.vm.scrollToIndex(10);
    expect(scrollTo).toHaveBeenLastCalledWith({
      top: 2000,
      behavior: "instant",
    });

    // Content above the list grows: the rows and the jump target follow it.
    above = 1500;
    ro.resize(document.body, 0, 6500);
    await nextTick();
    expect(tops(wrapper)[0]).toBe(0);
    wrapper.vm.scrollToIndex(10);
    expect(scrollTo).toHaveBeenLastCalledWith({
      top: 2500,
      behavior: "instant",
    });

    scrollTo.mockRestore();
    wrapper.unmount();
  });

  it("counts only the rows inside the viewport when the list starts below its top", async () => {
    const ro = stubResizeObserver();
    const wrapper = await mountPage();
    const inner = wrapper.get(".r-virtual-scroller__inner").element;
    let above = 350;
    vi.spyOn(inner, "getBoundingClientRect").mockImplementation(
      () => ({ top: above - window.scrollY }) as DOMRect,
    );
    ro.resize(document.body, 0, 6000);
    await nextTick();
    // 150px of a 500px viewport shows the list: rows 0 and 1.
    expect(tops(wrapper)).toEqual([0, 100]);

    // Entirely below the viewport: nothing to render or fetch.
    above = 800;
    ro.resize(document.body, 0, 6000);
    await nextTick();
    expect(tops(wrapper)).toEqual([]);
    expect(wrapper.emitted("update:viewportRange")?.at(-1)?.[0]).toEqual({
      first: 0,
      last: -1,
    });
    wrapper.unmount();
  });

  it("scrolls the window", async () => {
    const wrapper = await mountPage();
    const scrollTo = vi
      .spyOn(window, "scrollTo")
      .mockImplementation(((opts: ScrollToOptions) =>
        setPageScroll(opts.top ?? 0)) as typeof window.scrollTo);

    wrapper.vm.scrollTo(700);
    expect(scrollTo).toHaveBeenCalledWith({ top: 700, behavior: "instant" });
    expect(wrapper.vm.scrollTop).toBe(700);

    wrapper.vm.scrollToIndex(10, { smooth: true, stickyOffset: 50 });
    expect(scrollTo).toHaveBeenLastCalledWith({
      top: 950,
      behavior: "smooth",
    });
    scrollTo.mockRestore();
    wrapper.unmount();
  });
});
