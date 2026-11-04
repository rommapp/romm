import { mount } from "@vue/test-utils";
import { afterAll, beforeAll, describe, expect, it } from "vitest";
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
