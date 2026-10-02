import { mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ControllerDebug from "./ControllerDebug.vue";

const back = vi.fn();
vi.mock("vue-router", () => ({ useRouter: () => ({ back }) }));
vi.mock("vue-i18n");

function padHoldingB(held: boolean): Gamepad {
  const buttons = Array.from({ length: 17 }, (_, i) => ({
    pressed: held && i === 1,
    touched: held && i === 1,
    value: held && i === 1 ? 1 : 0,
  }));
  return {
    index: 0,
    id: "test-pad",
    connected: true,
    mapping: "standard",
    axes: [0, 0, 0, 0],
    buttons,
  } as unknown as Gamepad;
}

describe("ControllerDebug", () => {
  let frame: FrameRequestCallback | null = null;
  let pads: Gamepad[] = [];
  let now = 0;

  function step(at: number) {
    now = at;
    const pending = frame;
    frame = null;
    pending?.(at);
  }

  beforeEach(() => {
    frame = null;
    pads = [];
    now = 0;
    vi.stubGlobal("requestAnimationFrame", (cb: FrameRequestCallback) => {
      frame = cb;
      return 1;
    });
    vi.stubGlobal("cancelAnimationFrame", () => {
      frame = null;
    });
    vi.spyOn(performance, "now").mockImplementation(() => now);
    Object.defineProperty(navigator, "getGamepads", {
      value: () => pads,
      configurable: true,
    });
  });

  function render() {
    return mount(ControllerDebug, { shallow: true });
  }

  it("leaves once B has been held for the full hold, and only once", () => {
    render();
    pads = [padHoldingB(true)];

    step(0);
    step(699);
    expect(back).not.toHaveBeenCalled();

    step(700);
    step(1400);
    step(2100);

    expect(back).toHaveBeenCalledOnce();
  });

  it("starts the hold over when B is let go", () => {
    render();
    pads = [padHoldingB(true)];
    step(0);
    step(600);

    pads = [padHoldingB(false)];
    step(650);
    pads = [padHoldingB(true)];
    step(700);
    step(1300);

    expect(back).not.toHaveBeenCalled();
  });

  it("stops polling once the view unmounts", () => {
    const wrapper = render();
    step(0);
    expect(frame).not.toBeNull();

    wrapper.unmount();

    expect(frame).toBeNull();
  });
});
