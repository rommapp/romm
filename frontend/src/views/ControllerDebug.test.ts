import { mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { buttonsHolding, gamepadFixture } from "@/utils/gamepad.fixtures";
import ControllerDebug from "./ControllerDebug.vue";

const back = vi.fn();
const push = vi.fn();
vi.mock("vue-router", () => ({ useRouter: () => ({ back, push }) }));
vi.mock("vue-i18n");

function padHoldingB(held: boolean): Gamepad {
  return gamepadFixture({
    buttons: held ? buttonsHolding(1) : buttonsHolding(),
  });
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
    window.history.replaceState({ back: "/settings" }, "");
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

  it("keeps polling after leaving, firing again only on a fresh hold", () => {
    render();
    pads = [padHoldingB(true)];
    step(0);
    step(700);
    step(1400);
    expect(back).toHaveBeenCalledOnce();

    pads = [padHoldingB(false)];
    step(1500);
    pads = [padHoldingB(true)];
    step(1600);
    step(2300);

    expect(back).toHaveBeenCalledTimes(2);
  });

  it("goes home when there is no page to go back to", () => {
    window.history.replaceState(null, "");
    render();
    pads = [padHoldingB(true)];

    step(0);
    step(700);

    expect(back).not.toHaveBeenCalled();
    expect(push).toHaveBeenCalledWith({ name: "home" });
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
