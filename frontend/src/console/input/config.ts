import type { InputAction } from "./actions";

export interface InputConfig {
  rtl: boolean;
  repeat: { initialDelayMs: number; repeatEveryMs: number };
  deadzone: number;
  keyMap: Record<string, import("./actions").InputAction | undefined>;
  gamepad: {
    axesThreshold: number;
    axisToAction: {
      x: {
        neg: import("./actions").InputAction;
        pos: import("./actions").InputAction;
      };
      y: {
        neg: import("./actions").InputAction;
        pos: import("./actions").InputAction;
      };
    };
    buttons: Record<number, import("./actions").InputAction | undefined>;
  };
}

export const defaultInputConfig: InputConfig = {
  rtl: false,
  repeat: { initialDelayMs: 350, repeatEveryMs: 120 },
  deadzone: 0.2,
  keyMap: {
    ArrowUp: "moveUp",
    ArrowDown: "moveDown",
    ArrowLeft: "moveLeft",
    ArrowRight: "moveRight",
    Enter: "confirm",
    " ": "confirm",
    Backspace: "back",
    f: "toggleFavorite",
    F: "toggleFavorite",
    x: "delete",
    X: "delete",
    Tab: undefined,
  },
  gamepad: {
    axesThreshold: 0.5,
    axisToAction: {
      x: { neg: "moveLeft" as InputAction, pos: "moveRight" as InputAction },
      y: { neg: "moveUp" as InputAction, pos: "moveDown" as InputAction },
    },
    buttons: {
      0: "confirm",
      1: "back",
      2: "delete",
      3: "toggleFavorite",
      8: "back",
      9: "menu",
      // Standard mapping D-pad (12: Up, 13: Down, 14: Left, 15: Right)
      12: "moveUp",
      13: "moveDown",
      14: "moveLeft",
      15: "moveRight",
    },
  },
};
