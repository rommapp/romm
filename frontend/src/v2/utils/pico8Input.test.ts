import { afterEach, describe, expect, it, vi } from "vitest";
import { createPico8Input } from "./pico8Input";
import { PICO8_INPUT_BITS } from "./pico8Runtime";

const { left, right, up, down, a, b } = PICO8_INPUT_BITS;

/** A standard-mapping pad with the given buttons held and sticks centred. */
function pad(pressed: number[] = [], axes: number[] = [0, 0]): Gamepad {
  return {
    connected: true,
    buttons: Array.from({ length: 17 }, (_, index) => ({
      pressed: pressed.includes(index),
      touched: false,
      value: 0,
    })),
    axes,
  } as unknown as Gamepad;
}

function stubPads(...pads: (Gamepad | null)[]) {
  vi.stubGlobal("navigator", { getGamepads: () => pads });
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("createPico8Input", () => {
  describe("keyboard", () => {
    it("maps the arrow keys and Z/X, and claims only those", () => {
      const input = createPico8Input();

      expect(input.pressKey("ArrowLeft")).toBe(true);
      expect(input.pressKey("KeyZ")).toBe(true);
      expect(input.pressKey("KeyQ")).toBe(false);

      expect(input.read().keyHeld).toBe(left | a);
    });

    it("releases a held key", () => {
      const input = createPico8Input();
      input.pressKey("ArrowUp");
      input.releaseKey("ArrowUp");

      expect(input.read().keyHeld).toBe(0);
    });

    it("ignores a release for a key it never claimed", () => {
      const input = createPico8Input();
      input.pressKey("ArrowUp");
      input.releaseKey("KeyQ");

      expect(input.read().keyHeld).toBe(up);
    });
  });

  describe("btnp edge detection", () => {
    it("reports a button as down only on the frame it is pressed", () => {
      const input = createPico8Input();
      input.pressKey("KeyZ");

      expect(input.read().keyDown).toBe(a);
      expect(input.read().keyDown).toBe(0);
      expect(input.read().keyHeld).toBe(a);
    });

    it("reports it again after a release and a fresh press", () => {
      const input = createPico8Input();
      input.pressKey("KeyZ");
      input.read();
      input.releaseKey("KeyZ");
      input.read();
      input.pressKey("KeyZ");

      expect(input.read().keyDown).toBe(a);
    });

    it("does not mistake a second button for a repeat of the first", () => {
      const input = createPico8Input();
      input.pressKey("ArrowLeft");
      input.read();
      input.pressKey("KeyZ");

      const frame = input.read();
      expect(frame.keyDown).toBe(a);
      expect(frame.keyHeld).toBe(left | a);
    });
  });

  describe("gamepad", () => {
    it("maps face buttons and the d-pad", () => {
      stubPads(pad([0, 1, 12, 15]));
      const input = createPico8Input();

      expect(input.read().keyHeld).toBe(a | b | up | right);
    });

    it("reads a deflected stick as a direction", () => {
      stubPads(pad([], [-1, 0.8]));
      const input = createPico8Input();

      expect(input.read().keyHeld).toBe(left | down);
    });

    it("ignores a stick inside the dead zone", () => {
      stubPads(pad([], [0.4, -0.4]));
      const input = createPico8Input();

      expect(input.read().keyHeld).toBe(0);
    });

    // Firefox keeps disconnected entries whose stale analog values drift
    // across the threshold and press buttons on their own. #3851.
    it("skips a disconnected pad still listed by the browser", () => {
      const phantom = pad([0], [-1, -1]);
      Object.defineProperty(phantom, "connected", { value: false });
      stubPads(phantom);
      const input = createPico8Input();

      expect(input.read().keyHeld).toBe(0);
    });

    it("skips empty slots and merges every live pad", () => {
      stubPads(null, pad([0]), pad([1]));
      const input = createPico8Input();

      expect(input.read().keyHeld).toBe(a | b);
    });

    it("survives a browser with no gamepad support", () => {
      vi.stubGlobal("navigator", {});
      const input = createPico8Input();

      expect(input.read().keyHeld).toBe(0);
    });

    it("merges pad input with the keyboard", () => {
      stubPads(pad([0]));
      const input = createPico8Input();
      input.pressKey("ArrowLeft");

      expect(input.read().keyHeld).toBe(left | a);
    });
  });

  describe("on-screen controls", () => {
    it("holds and releases a bit, and exposes it for styling", () => {
      const input = createPico8Input();

      input.pressTouch(down);
      expect(input.touchMask.value).toBe(down);
      expect(input.read().keyHeld).toBe(down);

      input.releaseTouch(down);
      expect(input.touchMask.value).toBe(0);
      expect(input.read().keyHeld).toBe(0);
    });
  });

  describe("mouse", () => {
    it("scales a pointer offset to the 128x128 screen", () => {
      const input = createPico8Input();

      input.moveMouse(320, 160, 640, 640);

      const frame = input.read();
      expect(frame.mouseX).toBe(64);
      expect(frame.mouseY).toBe(32);
    });

    it("clamps to the screen instead of reporting a pixel off it", () => {
      const input = createPico8Input();

      input.moveMouse(640, 640, 640, 640);
      expect(input.read()).toMatchObject({ mouseX: 127, mouseY: 127 });

      input.moveMouse(-50, -50, 640, 640);
      expect(input.read()).toMatchObject({ mouseX: 0, mouseY: 0 });
    });

    it("keeps the last position when the canvas has collapsed", () => {
      const input = createPico8Input();
      input.moveMouse(320, 320, 640, 640);

      input.moveMouse(10, 10, 0, 0);

      expect(input.read()).toMatchObject({ mouseX: 64, mouseY: 64 });
    });

    it("maps left, middle and right to the masks FAKE-08 expects", () => {
      const input = createPico8Input();

      input.pressMouse(0);
      expect(input.read().mouseButtons).toBe(0x01);
      input.pressMouse(1);
      expect(input.read().mouseButtons).toBe(0x01 | 0x04);
      input.pressMouse(2);
      expect(input.read().mouseButtons).toBe(0x01 | 0x04 | 0x02);

      input.releaseMouse(1);
      expect(input.read().mouseButtons).toBe(0x01 | 0x02);
    });

    it("ignores a button it has no mask for", () => {
      const input = createPico8Input();
      input.pressMouse(0);

      input.pressMouse(4);

      expect(input.read().mouseButtons).toBe(0x01);
    });

    it("drops every button when capture is lost", () => {
      const input = createPico8Input();
      input.pressMouse(0);
      input.pressMouse(2);

      input.clearMouse();

      expect(input.read().mouseButtons).toBe(0);
    });
  });

  describe("reset", () => {
    it("clears every source so a replay starts clean", () => {
      stubPads();
      const input = createPico8Input();
      input.pressKey("ArrowLeft");
      input.pressTouch(a);
      input.pressMouse(0);
      input.moveMouse(640, 640, 640, 640);
      input.read();

      input.reset();

      expect(input.read()).toEqual({
        keyDown: 0,
        keyHeld: 0,
        mouseX: 0,
        mouseY: 0,
        mouseButtons: 0,
      });
      expect(input.touchMask.value).toBe(0);
    });

    it("re-arms edge detection, so a still-held button presses again", () => {
      const input = createPico8Input();
      input.pressKey("KeyZ");
      input.read();

      input.reset();
      input.pressKey("KeyZ");

      expect(input.read().keyDown).toBe(a);
    });
  });

  it("hands back the same struct each frame, so callers must not retain it", () => {
    const input = createPico8Input();

    expect(input.read()).toBe(input.read());
  });
});
