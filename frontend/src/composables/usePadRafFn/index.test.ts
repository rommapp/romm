import { mount } from "@vue/test-utils";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { defineComponent } from "vue";
import { gamepadFixture } from "@/utils/gamepad.fixtures";
import { usePadRafFn } from "./index";

describe("usePadRafFn", () => {
  let frame: FrameRequestCallback | null = null;
  let pads: (Gamepad | null)[] = [];
  let ticks = 0;

  beforeEach(() => {
    frame = null;
    pads = [];
    ticks = 0;
    vi.useFakeTimers({ toFake: ["setInterval", "clearInterval"] });
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

  afterEach(() => {
    vi.useRealTimers();
  });

  function mountHost() {
    return mount(
      defineComponent({
        setup() {
          usePadRafFn(() => ticks++);
          return () => null;
        },
      }),
    );
  }

  it("does not poll until a pad connects", () => {
    // Act
    mountHost();

    // Assert
    expect(frame).toBeNull();
  });

  it("polls from mount when a pad is already exposed", () => {
    // Arrange
    pads = [gamepadFixture()];

    // Act
    mountHost();
    frame?.(0);

    // Assert
    expect(ticks).toBe(1);
  });

  it("starts polling when a pad connects", () => {
    // Arrange
    mountHost();

    // Act
    window.dispatchEvent(new Event("gamepadconnected"));

    // Assert
    expect(frame).not.toBeNull();
  });

  it("starts polling when a pad appears without a connect event", () => {
    // Arrange
    mountHost();
    pads = [gamepadFixture()];

    // Act
    vi.advanceTimersByTime(1000);

    // Assert
    expect(frame).not.toBeNull();
  });

  it("probes again after the last pad disconnects", () => {
    // Arrange
    mountHost();
    window.dispatchEvent(new Event("gamepadconnected"));
    window.dispatchEvent(new Event("gamepaddisconnected"));
    pads = [gamepadFixture()];

    // Act
    vi.advanceTimersByTime(1000);

    // Assert
    expect(frame).not.toBeNull();
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

  it("stops polling once the last pad disconnects", () => {
    // Arrange
    mountHost();
    window.dispatchEvent(new Event("gamepadconnected"));

    // Act
    window.dispatchEvent(new Event("gamepaddisconnected"));

    // Assert
    expect(frame).toBeNull();
  });

  it("keeps polling while another pad stays connected", () => {
    // Arrange
    mountHost();
    window.dispatchEvent(new Event("gamepadconnected"));
    pads = [gamepadFixture()];

    // Act
    window.dispatchEvent(new Event("gamepaddisconnected"));

    // Assert
    expect(frame).not.toBeNull();
  });
});
