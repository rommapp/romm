import { mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { nextTick } from "vue";
import { stubResizeObserver } from "@/test-utils/resizeObserver";
import RSliderBtnGroup from "./RSliderBtnGroup.vue";

describe("RSliderBtnGroup resize", () => {
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
    const wrapper = mount(RSliderBtnGroup, {
      props: {
        modelValue: "a",
        items: [
          { id: "a", label: "A" },
          { id: "b", label: "B" },
        ],
      },
      global: { stubs: { RTooltip: true } },
    });
    await nextTick();
    await nextTick();
    step();
    return wrapper;
  }

  it("snaps into place without sliding when a hidden group is shown", async () => {
    const wrapper = await render();
    const group = wrapper.get(".r-slider-btn-group").element;
    const animated = () =>
      wrapper
        .get(".r-slider-btn-group__indicator")
        .classes("r-slider-btn-group__indicator--animate");
    expect(animated()).toBe(true);

    vi.spyOn(group, "getBoundingClientRect").mockReturnValue(
      new DOMRect(0, 0, 120, 28),
    );
    ro.resize(group, 120);
    await nextTick();
    expect(animated()).toBe(false);

    step();
    await nextTick();
    expect(animated()).toBe(true);
  });

  it("stops observing on unmount", async () => {
    const wrapper = await render();
    const group = wrapper.get(".r-slider-btn-group").element;
    expect(ro.isObserved(group)).toBe(true);

    wrapper.unmount();

    expect(ro.isObserved(group)).toBe(false);
  });
});
