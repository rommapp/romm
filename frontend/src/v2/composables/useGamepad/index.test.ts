import { mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { defineComponent } from "vue";
import storePlaying from "@/stores/playing";
import { useInputModality } from "@/v2/composables/useInputModality";
import { AXIS_THRESHOLD, PAD_BUTTON, useGamepad } from "./index";

vi.mock("vue-router", () => ({
  useRoute: () => ({ path: "/platforms" }),
  useRouter: () => ({ push: vi.fn(), back: vi.fn() }),
}));

const PUSHED = AXIS_THRESHOLD + 0.2;

const noHaptics: GamepadHapticActuator = {
  playEffect: () => Promise.resolve("complete"),
  reset: () => Promise.resolve("complete"),
};

function padWithStick(x: number, y: number): Gamepad {
  return {
    index: 0,
    id: "test-pad",
    connected: true,
    mapping: "standard",
    axes: [x, y],
    buttons: [],
    timestamp: 0,
    vibrationActuator: noHaptics,
  };
}

function padHolding(button: number): Gamepad {
  const buttons = Array.from({ length: 17 }, (_, i) => ({
    pressed: i === button,
    touched: i === button,
    value: i === button ? 1 : 0,
  }));
  return { ...padWithStick(0, 0), buttons };
}

describe("useGamepad", () => {
  const { modality, setModality } = useInputModality();
  let wrapper: ReturnType<typeof mount> | null = null;
  let frame: FrameRequestCallback | null = null;
  let keys: string[] = [];

  function onKeydown(e: KeyboardEvent) {
    keys.push(e.key);
  }

  // Runs one poll of the RAF loop install() armed; the loop re-arms itself.
  function step() {
    const pending = frame;
    frame = null;
    pending?.(0);
  }

  // Seeing a pad at install flips the modality, so hand the session back to
  // the mouse: these tests are about the user who launched with a click.
  function installOnMouse(pad: Gamepad) {
    Object.defineProperty(navigator, "getGamepads", {
      value: () => [pad],
      configurable: true,
    });
    wrapper = mount(
      defineComponent({
        setup() {
          useGamepad().install();
          return () => null;
        },
      }),
    );
    setModality("mouse");
  }

  beforeEach(() => {
    setActivePinia(createPinia());
    keys = [];
    frame = null;
    vi.stubGlobal("requestAnimationFrame", (cb: FrameRequestCallback) => {
      frame = cb;
      return 1;
    });
    vi.stubGlobal("cancelAnimationFrame", () => {});
    window.addEventListener("keydown", onKeydown);
    // Live so the suite sees the tracker ignore the synthetic arrows.
    useInputModality().install();
  });

  afterEach(() => {
    window.removeEventListener("keydown", onKeydown);
    wrapper?.unmount();
    wrapper = null;
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("steers with the left stick", () => {
    installOnMouse(padWithStick(PUSHED, 0));

    step();

    expect(keys).toEqual(["ArrowRight"]);
  });

  it("reads stick motion as pad input, not as the keypress it synthesises", () => {
    installOnMouse(padWithStick(0, -PUSHED));

    step();

    expect(keys).toEqual(["ArrowUp"]);
    expect(modality.value).toBe("pad");
  });

  it("still claims the pad while the emulator owns the stick", () => {
    installOnMouse(padWithStick(PUSHED, 0));
    storePlaying().setPlaying(true);

    step();

    expect(keys).toEqual([]);
    expect(modality.value).toBe("pad");
  });

  it("keeps a held d-pad on the pad as it repeats", () => {
    const now = vi.spyOn(performance, "now").mockReturnValue(0);
    installOnMouse(padHolding(PAD_BUTTON["dpad-down"]));

    step();
    now.mockReturnValue(1000);
    step();

    expect(keys).toEqual(["ArrowDown", "ArrowDown"]);
    expect(modality.value).toBe("pad");
  });

  it("ignores a stick resting below the threshold", () => {
    installOnMouse(padWithStick(AXIS_THRESHOLD - 0.1, 0));

    step();

    expect(keys).toEqual([]);
    expect(modality.value).toBe("mouse");
  });
});
