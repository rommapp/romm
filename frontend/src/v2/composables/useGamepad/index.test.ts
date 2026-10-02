import { mount } from "@vue/test-utils";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { defineComponent } from "vue";
import storePlaying from "@/stores/playing";
import { useInputModality } from "@/v2/composables/useInputModality";
import {
  popEscapable,
  pushEscapable,
} from "@/v2/lib/overlays/RDialog/escapeStack";
import {
  AXIS_THRESHOLD,
  EXIT_CHORD_HOLD_MS,
  isPadEvent,
  PAD_BUTTON,
  useGamepad,
} from "./index";

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

function padHolding(...held: number[]): Gamepad {
  const buttons = Array.from({ length: 17 }, (_, i) => ({
    pressed: held.includes(i),
    touched: held.includes(i),
    value: held.includes(i) ? 1 : 0,
  }));
  return { ...padWithStick(0, 0), buttons };
}

describe("useGamepad", () => {
  const { modality, setModality } = useInputModality();
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
  function installOnMouse(pad: Gamepad | (() => Gamepad[])) {
    Object.defineProperty(navigator, "getGamepads", {
      value: typeof pad === "function" ? pad : () => [pad],
      configurable: true,
    });
    mount(
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

  it("flags the arrows it dispatches as pad input", () => {
    const flags: boolean[] = [];
    const record = (e: KeyboardEvent) => flags.push(isPadEvent(e));
    window.addEventListener("keydown", record);
    installOnMouse(padHolding(PAD_BUTTON["dpad-up"]));

    step();
    window.removeEventListener("keydown", record);

    expect(flags).toEqual([true]);
    expect(isPadEvent(new KeyboardEvent("keydown", { key: "ArrowUp" }))).toBe(
      false,
    );
  });

  describe("exit chord", () => {
    const CHORD = [PAD_BUTTON.back, PAD_BUTTON.start];
    let pads: Gamepad[] = [];
    let chords = 0;
    const onChord = () => chords++;
    let now: ReturnType<typeof vi.spyOn>;

    // Polls once at `ms` past the clock's start.
    function stepAt(ms: number) {
      now.mockReturnValue(1000 + ms);
      step();
    }

    beforeEach(() => {
      pads = [];
      chords = 0;
      now = vi.spyOn(performance, "now").mockReturnValue(1000);
      window.addEventListener("gamepad:exitchord", onChord);
      installOnMouse(() => pads);
      storePlaying().setPlaying(true);
    });

    afterEach(() => {
      window.removeEventListener("gamepad:exitchord", onChord);
    });

    it("fires once Select+Start has been held for the full hold", () => {
      pads = [padHolding(...CHORD)];

      stepAt(0);
      stepAt(EXIT_CHORD_HOLD_MS - 1);
      expect(chords).toBe(0);
      stepAt(EXIT_CHORD_HOLD_MS);
      expect(chords).toBe(1);
    });

    it("waits for a release before a held chord can fire again", () => {
      pads = [padHolding(...CHORD)];
      stepAt(0);
      stepAt(EXIT_CHORD_HOLD_MS);
      stepAt(EXIT_CHORD_HOLD_MS * 3);
      expect(chords).toBe(1);

      pads = [padHolding()];
      stepAt(EXIT_CHORD_HOLD_MS * 3 + 100);
      pads = [padHolding(...CHORD)];
      stepAt(EXIT_CHORD_HOLD_MS * 4);
      stepAt(EXIT_CHORD_HOLD_MS * 5);
      expect(chords).toBe(2);
    });

    it("starts the hold over when either button is let go", () => {
      pads = [padHolding(...CHORD)];
      stepAt(0);
      pads = [padHolding(PAD_BUTTON.back)];
      stepAt(1000);
      pads = [padHolding(...CHORD)];
      stepAt(1100);
      stepAt(1100 + EXIT_CHORD_HOLD_MS - 1);

      expect(chords).toBe(0);
    });

    it("ignores a disconnected pad's stale buttons", () => {
      // Firefox keeps disconnected entries in getGamepads() (#3851).
      pads = [{ ...padHolding(...CHORD), connected: false }];
      stepAt(0);
      stepAt(EXIT_CHORD_HOLD_MS * 2);

      expect(chords).toBe(0);
    });

    it("ignores pads without the standard mapping", () => {
      pads = [{ ...padHolding(...CHORD), mapping: "" }];
      stepAt(0);
      stepAt(EXIT_CHORD_HOLD_MS * 2);

      expect(chords).toBe(0);
    });

    it("stays quiet outside a game, where Select and Start drive the app", () => {
      storePlaying().setPlaying(false);
      pads = [padHolding(...CHORD)];
      stepAt(0);
      stepAt(EXIT_CHORD_HOLD_MS * 2);

      expect(chords).toBe(0);
    });

    it("holds off while an overlay sits over the game", () => {
      const dialog = { close: () => {}, persistent: true };
      pushEscapable(dialog);
      try {
        pads = [padHolding(...CHORD)];
        stepAt(0);
        stepAt(EXIT_CHORD_HOLD_MS * 2);
      } finally {
        popEscapable(dialog);
      }

      expect(chords).toBe(0);
    });

    it("stays fired after its dialog closes while the chord is still held", () => {
      const dialog = { close: () => {}, persistent: false };
      pads = [padHolding(...CHORD)];
      stepAt(0);
      stepAt(EXIT_CHORD_HOLD_MS);
      expect(chords).toBe(1);

      pushEscapable(dialog);
      try {
        stepAt(EXIT_CHORD_HOLD_MS + 100);
      } finally {
        popEscapable(dialog);
      }
      stepAt(EXIT_CHORD_HOLD_MS * 3);
      stepAt(EXIT_CHORD_HOLD_MS * 5);

      expect(chords).toBe(1);
    });
  });
});
