import { mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { defineComponent, ref } from "vue";
import { gamepadFixture } from "@/utils/gamepad.fixtures";
import { useRightStickScroll } from "./index";

function padWithRightStick(x: number, y: number): Gamepad {
  return gamepadFixture({ axes: [0, 0, x, y] });
}

describe("useRightStickScroll", () => {
  let frame: FrameRequestCallback | null = null;
  let pads: (Gamepad | null)[] = [];

  function step() {
    const pending = frame;
    frame = null;
    pending?.(0);
  }

  beforeEach(() => {
    frame = null;
    pads = [];
    vi.stubGlobal("requestAnimationFrame", (cb: FrameRequestCallback) => {
      frame = cb;
      return 1;
    });
    vi.stubGlobal("cancelAnimationFrame", () => {
      frame = null;
    });
    Object.defineProperty(navigator, "getGamepads", {
      value: () => pads,
      configurable: true,
    });
  });

  function setup() {
    const el = document.createElement("div");
    const host = mount(
      defineComponent({
        setup() {
          useRightStickScroll(ref(el));
          return () => null;
        },
      }),
    );
    return { el, host };
  }

  it("scrolls by the stick's deflection every frame", () => {
    const { el } = setup();
    pads = [padWithRightStick(0.5, 1)];

    step();
    step();

    expect(el.scrollTop).toBe(50);
    expect(el.scrollLeft).toBe(25);
  });

  it("follows the most deflected stick across pads", () => {
    const { el } = setup();
    pads = [null, padWithRightStick(0, 0.4), padWithRightStick(0, 0.8)];

    step();

    expect(el.scrollTop).toBe(20);
  });

  it("ignores a stick resting inside the deadzone", () => {
    const { el } = setup();
    pads = [padWithRightStick(0.1, 0.1)];

    step();

    expect(el.scrollTop).toBe(0);
    expect(el.scrollLeft).toBe(0);
  });

  it("stops polling once its host unmounts", () => {
    const { host } = setup();
    expect(frame).not.toBeNull();

    host.unmount();

    expect(frame).toBeNull();
  });
});
