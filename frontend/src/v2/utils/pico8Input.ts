// Gathers keyboard, gamepad, on-screen and mouse state into the per-frame
// snapshot FAKE-08 expects, so the view is left with DOM plumbing only.
import { ref, type Ref } from "vue";
import {
  AXIS_THRESHOLD,
  isUsablePad,
  PAD_BUTTON,
} from "@/v2/composables/useGamepad";
import {
  PICO8_HEIGHT,
  PICO8_INPUT_BITS,
  PICO8_WIDTH,
  type Pico8Input,
} from "./pico8Runtime";

const keyboardBits: Record<string, number> = {
  ArrowLeft: PICO8_INPUT_BITS.left,
  ArrowRight: PICO8_INPUT_BITS.right,
  ArrowUp: PICO8_INPUT_BITS.up,
  ArrowDown: PICO8_INPUT_BITS.down,
  KeyZ: PICO8_INPUT_BITS.a,
  KeyX: PICO8_INPUT_BITS.b,
};

const padButtonBits = [
  [PAD_BUTTON.a, PICO8_INPUT_BITS.a],
  [PAD_BUTTON.b, PICO8_INPUT_BITS.b],
  [PAD_BUTTON["dpad-up"], PICO8_INPUT_BITS.up],
  [PAD_BUTTON["dpad-down"], PICO8_INPUT_BITS.down],
  [PAD_BUTTON["dpad-left"], PICO8_INPUT_BITS.left],
  [PAD_BUTTON["dpad-right"], PICO8_INPUT_BITS.right],
] as const;

// Per stick axis, the bit for a negative then a positive deflection.
const padAxisBits = [
  [PICO8_INPUT_BITS.left, PICO8_INPUT_BITS.right],
  [PICO8_INPUT_BITS.up, PICO8_INPUT_BITS.down],
] as const;

// Pointer button number to the mask FAKE-08 expects (left, middle, right).
const mouseButtonBits = [0x01, 0x04, 0x02];

function clampToScreen(value: number, size: number) {
  return Math.max(0, Math.min(size - 1, Math.floor(value)));
}

function readGamepadBits() {
  let mask = 0;
  for (const gamepad of navigator.getGamepads?.() ?? []) {
    if (!isUsablePad(gamepad)) continue;
    const { buttons, axes } = gamepad;
    for (const [index, bit] of padButtonBits) {
      if (buttons[index]?.pressed) mask |= bit;
    }
    for (let axis = 0; axis < padAxisBits.length; axis += 1) {
      const value = axes[axis] ?? 0;
      if (value < -AXIS_THRESHOLD) mask |= padAxisBits[axis][0];
      if (value > AXIS_THRESHOLD) mask |= padAxisBits[axis][1];
    }
  }
  return mask;
}

export interface Pico8InputSource {
  /** Held bits from the on-screen pad, for the pressed styling. */
  touchMask: Ref<number>;
  /**
   * Snapshot the current state for one emulated frame.
   *
   * @returns A reused struct, so read it before the next call.
   */
  read: () => Pico8Input;
  /**
   * @param code A `KeyboardEvent.code`.
   * @returns True when it maps to a PICO-8 button, so the caller can consume it.
   */
  pressKey: (code: string) => boolean;
  releaseKey: (code: string) => void;
  pressTouch: (bit: number) => void;
  releaseTouch: (bit: number) => void;
  /**
   * Place the cart's mouse from a pointer offset inside the canvas.
   *
   * @param offsetX Pointer position from the canvas' left edge, in CSS pixels.
   * @param offsetY Pointer position from the canvas' top edge, in CSS pixels.
   * @param width Rendered canvas width.
   * @param height Rendered canvas height.
   */
  moveMouse: (
    offsetX: number,
    offsetY: number,
    width: number,
    height: number,
  ) => void;
  pressMouse: (button: number) => void;
  releaseMouse: (button: number) => void;
  clearMouse: () => void;
  reset: () => void;
}

/**
 * Build the input source backing one play session.
 *
 * @returns The source.
 */
export function createPico8Input(): Pico8InputSource {
  const touchMask = ref(0);
  const snapshot: Pico8Input = {
    keyDown: 0,
    keyHeld: 0,
    mouseX: 0,
    mouseY: 0,
    mouseButtons: 0,
  };

  let keyboardMask = 0;
  let previousHeld = 0;
  let mouseX = 0;
  let mouseY = 0;
  let mouseButtons = 0;

  return {
    touchMask,

    read() {
      const held = keyboardMask | touchMask.value | readGamepadBits();
      // PICO-8's btnp() asks which buttons went down this frame.
      snapshot.keyDown = held & ~previousHeld;
      snapshot.keyHeld = held;
      snapshot.mouseX = mouseX;
      snapshot.mouseY = mouseY;
      snapshot.mouseButtons = mouseButtons;
      previousHeld = held;
      return snapshot;
    },

    pressKey(code) {
      const bit = keyboardBits[code];
      if (!bit) return false;
      keyboardMask |= bit;
      return true;
    },

    releaseKey(code) {
      const bit = keyboardBits[code];
      if (bit) keyboardMask &= ~bit;
    },

    pressTouch(bit) {
      touchMask.value |= bit;
    },

    releaseTouch(bit) {
      touchMask.value &= ~bit;
    },

    moveMouse(offsetX, offsetY, width, height) {
      // A collapsed canvas would divide by zero, and the cart keeps the
      // position it already had.
      if (width === 0 || height === 0) return;
      mouseX = clampToScreen((offsetX / width) * PICO8_WIDTH, PICO8_WIDTH);
      mouseY = clampToScreen((offsetY / height) * PICO8_HEIGHT, PICO8_HEIGHT);
    },

    pressMouse(button) {
      mouseButtons |= mouseButtonBits[button] ?? 0;
    },

    releaseMouse(button) {
      mouseButtons &= ~(mouseButtonBits[button] ?? 0);
    },

    clearMouse() {
      mouseButtons = 0;
    },

    reset() {
      keyboardMask = 0;
      previousHeld = 0;
      mouseX = 0;
      mouseY = 0;
      mouseButtons = 0;
      touchMask.value = 0;
    },
  };
}
