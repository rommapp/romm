import { mount } from "@vue/test-utils";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { defineComponent, h, nextTick, ref } from "vue";
import { useInputModality } from "@/composables/useInputModality";
import {
  popEscapable,
  pushEscapable,
} from "@/lib/overlays/RDialog/escapeStack";
import storePlaying from "@/stores/playing";
import { buttonsHolding, gamepadFixture } from "@/utils/gamepad.fixtures";
import {
  AXIS_THRESHOLD,
  EXIT_CHORD_HOLD_MS,
  isPadEvent,
  PAD_BUTTON,
  useGamepad,
} from "./index";

const router = vi.hoisted(() => ({ push: vi.fn(), back: vi.fn() }));
const route = vi.hoisted(() => ({ path: "/platforms" }));

vi.mock("vue-router", () => ({
  useRoute: () => route,
  useRouter: () => router,
}));

const PUSHED = AXIS_THRESHOLD + 0.2;

function padWithStick(x: number, y: number): Gamepad {
  return gamepadFixture({ axes: [x, y] });
}

function padHolding(...held: number[]): Gamepad {
  return gamepadFixture({ buttons: buttonsHolding(...held) });
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
    const host = mount(
      defineComponent({
        setup() {
          useGamepad().install();
          return () => null;
        },
      }),
    );
    setModality("mouse");
    return host;
  }

  beforeEach(() => {
    keys = [];
    frame = null;
    vi.stubGlobal("requestAnimationFrame", (cb: FrameRequestCallback) => {
      frame = cb;
      return 1;
    });
    vi.stubGlobal("cancelAnimationFrame", () => {
      frame = null;
    });
    window.addEventListener("keydown", onKeydown);
    // Live so the suite sees the tracker ignore the synthetic arrows.
    useInputModality().install();
  });

  afterEach(() => {
    window.removeEventListener("keydown", onKeydown);
  });

  it("stops polling once its host unmounts, and installs again on the next", () => {
    const getGamepads = vi.fn(() => [padWithStick(0, 0)]);
    const host = installOnMouse(getGamepads);
    step();
    const polls = getGamepads.mock.calls.length;

    host.unmount();
    step();
    expect(getGamepads).toHaveBeenCalledTimes(polls);

    installOnMouse(getGamepads);
    step();
    expect(getGamepads.mock.calls.length).toBeGreaterThan(polls);
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

  describe("bumpers", () => {
    afterEach(() => {
      route.path = "/platforms";
    });

    it("steps to the next section from a gallery under one", () => {
      route.path = "/platform/12";
      installOnMouse(padHolding(PAD_BUTTON.rb));

      step();

      expect(router.push).toHaveBeenCalledWith("/collections");
    });

    it("wraps from the first section back to the last", () => {
      route.path = "/";
      installOnMouse(padHolding(PAD_BUTTON.lb));

      step();

      expect(router.push).toHaveBeenCalledWith("/search");
    });

    it("lands on Home from a page outside the sections", () => {
      route.path = "/rom/7";
      installOnMouse(padHolding(PAD_BUTTON.rb));

      step();

      expect(router.push).toHaveBeenCalledWith("/");
    });
  });

  describe("A", () => {
    afterEach(() => {
      document.body.innerHTML = "";
    });

    function focusField(html: string) {
      document.body.innerHTML = html;
      const field = document.querySelector<HTMLElement>("[data-field]")!;
      field.focus();
      return field;
    }

    it("clicks the focused control", async () => {
      const field = focusField("<button data-field>Go</button>");
      const click = vi.fn();
      field.addEventListener("click", click);

      installOnMouse(padHolding(PAD_BUTTON.a));
      step();
      await nextTick();

      expect(click).toHaveBeenCalledOnce();
    });

    it("leaves a text field alone", async () => {
      const field = focusField("<input data-field />");
      const click = vi.fn();
      field.addEventListener("click", click);

      installOnMouse(padHolding(PAD_BUTTON.a));
      step();
      await nextTick();

      expect(click).not.toHaveBeenCalled();
    });

    it.each([
      ["button", "button", "</button>"],
      ["search field", "input", ""],
    ])(
      "picks the active option of an open %s combobox",
      async (_, tag, close) => {
        const field = focusField(
          `<${tag} data-field role="combobox" aria-expanded="true" aria-activedescendant="opt-2">${close}` +
            '<ul role="listbox"><li id="opt-1" role="option">1</li><li id="opt-2" role="option">2</li></ul>',
        );
        const picked = vi.fn();
        document.getElementById("opt-2")!.addEventListener("click", picked);
        const fieldClick = vi.fn();
        field.addEventListener("click", fieldClick);

        installOnMouse(padHolding(PAD_BUTTON.a));
        step();
        await nextTick();

        expect(picked).toHaveBeenCalledOnce();
        expect(fieldClick).not.toHaveBeenCalled();
      },
    );

    it("clicks a closed combobox itself", async () => {
      const field = focusField(
        '<button data-field role="combobox" aria-expanded="false" aria-activedescendant="opt-1"></button>' +
          '<li id="opt-1" role="option">1</li>',
      );
      const click = vi.fn();
      field.addEventListener("click", click);

      installOnMouse(padHolding(PAD_BUTTON.a));
      step();
      await nextTick();

      expect(click).toHaveBeenCalledOnce();
    });

    it.each([
      ["checkbox", '<input data-field type="checkbox" />'],
      ["read-only field", '<input data-field readonly value="Mar 15, 2024" />'],
    ])("clicks a focused %s", async (_, html) => {
      const field = focusField(html);
      const click = vi.fn();
      field.addEventListener("click", click);

      installOnMouse(padHolding(PAD_BUTTON.a));
      step();
      await nextTick();

      expect(click).toHaveBeenCalledOnce();
    });

    it("picks the option a D-pad press in the same poll moved to", async () => {
      const active = ref(1);
      const picked = vi.fn();
      mount(
        defineComponent(() => () => [
          h("button", {
            "data-field": "",
            role: "combobox",
            "aria-expanded": "true",
            "aria-activedescendant": `opt-${active.value}`,
            onKeydown: (e: KeyboardEvent) => {
              if (e.key === "ArrowDown") active.value += 1;
            },
          }),
          [1, 2].map((n) =>
            h("li", {
              id: `opt-${n}`,
              role: "option",
              onClick: () => picked(n),
            }),
          ),
        ]),
        { attachTo: document.body },
      );
      document.querySelector<HTMLElement>("[data-field]")!.focus();

      installOnMouse(padHolding(PAD_BUTTON.a, PAD_BUTTON["dpad-down"]));
      step();
      await nextTick();

      expect(picked.mock.calls).toEqual([[2]]);
    });
  });

  describe("B", () => {
    it("goes back when nothing claims the Escape it sends", () => {
      installOnMouse(padHolding(PAD_BUTTON.b));

      step();

      expect(keys).toEqual(["Escape"]);
      expect(router.back).toHaveBeenCalledOnce();
    });

    it.each([
      { persistent: false, closes: 1 },
      { persistent: true, closes: 0 },
    ])(
      "dismisses an overlay (persistent: $persistent) instead of going back",
      ({ persistent, closes }) => {
        const close = vi.fn();
        const dialog = { close, persistent };
        pushEscapable(dialog);
        try {
          installOnMouse(padHolding(PAD_BUTTON.b));
          step();
        } finally {
          popEscapable(dialog);
        }

        expect(close).toHaveBeenCalledTimes(closes);
        expect(router.back).not.toHaveBeenCalled();
      },
    );

    it("leaves history alone when a view's Escape handler claims the press", () => {
      const claim = (e: KeyboardEvent) => {
        if (e.key === "Escape") e.preventDefault();
      };
      window.addEventListener("keydown", claim);
      try {
        installOnMouse(padHolding(PAD_BUTTON.b));
        step();
      } finally {
        window.removeEventListener("keydown", claim);
      }

      expect(router.back).not.toHaveBeenCalled();
    });
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
