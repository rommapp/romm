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
    const mounted = mountHost();
    window.dispatchEvent(new Event("gamepadconnected"));
    return mounted;
  }

  function mountHost() {
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

  it("does not poll until a pad connects", () => {
    // Arrange
    pads = [];

    // Act
    mountHost();

    // Assert
    expect(frame).toBeNull();
  });

  it("stays idle when a Permissions-Policy blocks the gamepad API", () => {
    // Arrange
    Object.defineProperty(navigator, "getGamepads", {
      value: () => {
        throw new DOMException(
          "Blocked by Permissions Policy",
          "SecurityError",
        );
      },
      configurable: true,
    });

    // Act
    mountHost();

    // Assert
    expect(frame).toBeNull();
  });

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

  it("ignores a disconnected pad's stale stick", () => {
    // Firefox keeps disconnected entries in getGamepads() (#3851).
    const { el } = setup();
    pads = [{ ...padWithRightStick(0, 1), connected: false }];

    step();

    expect(el.scrollTop).toBe(0);
  });

  it("ignores a stick resting inside the deadzone", () => {
    const { el } = setup();
    pads = [padWithRightStick(0.1, 0.1)];

    step();

    expect(el.scrollTop).toBe(0);
    expect(el.scrollLeft).toBe(0);
  });

  it("stops polling once the last pad disconnects", () => {
    // Arrange
    setup();
    pads = [];

    // Act
    window.dispatchEvent(new Event("gamepaddisconnected"));

    // Assert
    expect(frame).toBeNull();
  });

  it("keeps polling while another pad stays connected", () => {
    // Arrange
    const { el } = setup();
    pads = [padWithRightStick(0, 1)];

    // Act
    window.dispatchEvent(new Event("gamepaddisconnected"));
    step();

    // Assert
    expect(el.scrollTop).toBe(25);
  });

  it("stops polling once its host unmounts", () => {
    const { host } = setup();
    expect(frame).not.toBeNull();

    host.unmount();

    expect(frame).toBeNull();
  });
});
