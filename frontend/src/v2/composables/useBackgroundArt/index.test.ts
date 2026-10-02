/* eslint-disable vue/one-component-per-file */
import { mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { defineComponent, h } from "vue";
import {
  provideBackgroundArt,
  type SetBackgroundArt,
  useBackgroundArt,
} from "./index";

function mountLayout() {
  let set: SetBackgroundArt = () => undefined;
  const Child = defineComponent({
    setup() {
      set = useBackgroundArt();
      return () => h("div");
    },
  });
  let layers!: ReturnType<typeof provideBackgroundArt>;
  const Layout = defineComponent({
    setup() {
      layers = provideBackgroundArt();
      return () => h(Child);
    },
  });
  const wrapper = mount(Layout);
  const shown = () =>
    layers.activeLayer.value === "a"
      ? layers.layerA.value
      : layers.layerB.value;
  return { wrapper, set, shown };
}

describe("provideBackgroundArt", () => {
  beforeEach(() =>
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] }),
  );

  it("cross-fades to the latest art once the pointer dwells", () => {
    const { set, shown } = mountLayout();

    set("a.png");
    vi.advanceTimersByTime(40);
    set("b.png");
    vi.advanceTimersByTime(79);
    expect(shown()).toBeNull();

    vi.advanceTimersByTime(1);
    expect(shown()).toBe("b.png");
  });

  it("drops a pending swap when the shown art is asked for again", () => {
    const { set, shown } = mountLayout();
    set("a.png");
    vi.advanceTimersByTime(80);

    set("b.png");
    set("a.png");
    vi.advanceTimersByTime(80);

    expect(shown()).toBe("a.png");
  });

  it("drops a pending swap on unmount", () => {
    const { wrapper, set, shown } = mountLayout();

    set("a.png");
    wrapper.unmount();
    vi.advanceTimersByTime(80);

    expect(shown()).toBeNull();
  });
});
