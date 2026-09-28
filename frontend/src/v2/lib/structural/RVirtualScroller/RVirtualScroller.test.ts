import { mount } from "@vue/test-utils";
import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { nextTick } from "vue";
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
