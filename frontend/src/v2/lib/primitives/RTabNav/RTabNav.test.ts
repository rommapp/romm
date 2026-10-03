import { mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { nextTick } from "vue";
import { stubResizeObserver } from "@/test-utils/resizeObserver";
import RTabNav from "./RTabNav.vue";

function sized(el: Element, left: number, width: number) {
  vi.spyOn(el, "getBoundingClientRect").mockReturnValue(
    new DOMRect(left, 0, width, 32),
  );
}

describe("RTabNav resize", () => {
  let frames: FrameRequestCallback[] = [];
  let ro: ReturnType<typeof stubResizeObserver>;

  function step() {
    const pending = frames;
    frames = [];
    pending.forEach((cb) => cb(0));
  }

  beforeEach(() => {
    frames = [];
    vi.stubGlobal("requestAnimationFrame", (cb: FrameRequestCallback) => {
      frames.push(cb);
      return frames.length;
    });
    ro = stubResizeObserver();
  });

  async function render() {
    const wrapper = mount(RTabNav, {
      props: {
        modelValue: "b",
        items: [
          { id: "a", label: "A" },
          { id: "b", label: "B" },
        ],
      },
    });
    await nextTick();
    await nextTick();
    step();
    return wrapper;
  }

  const track = (w: Awaited<ReturnType<typeof render>>) =>
    w.get(".r-tab-nav__track").element;
  const indicator = (w: Awaited<ReturnType<typeof render>>) =>
    w.get(".r-tab-nav__indicator");

  it("re-measures the indicator when the strip resizes", async () => {
    const wrapper = await render();
    sized(track(wrapper), 0, 300);
    sized(wrapper.findAll("button[role='tab']")[1].element, 80, 60);

    ro.resize(track(wrapper), 300);
    await nextTick();

    expect(indicator(wrapper).attributes("style")).toContain(
      "translateX(80px)",
    );
    expect(indicator(wrapper).attributes("style")).toContain("width: 60px");
  });

  it("snaps into place without sliding when a hidden strip is shown", async () => {
    const wrapper = await render();
    const animated = () =>
      indicator(wrapper).classes("r-tab-nav__indicator--animate");
    expect(animated()).toBe(true);

    sized(track(wrapper), 0, 300);
    ro.resize(track(wrapper), 300);
    await nextTick();
    expect(animated()).toBe(false);

    step();
    await nextTick();
    expect(animated()).toBe(true);
  });

  it("stops observing on unmount", async () => {
    const wrapper = await render();
    const el = track(wrapper);
    expect(ro.isObserved(el)).toBe(true);

    wrapper.unmount();

    expect(ro.isObserved(el)).toBe(false);
  });
});
