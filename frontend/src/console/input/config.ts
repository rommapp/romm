export interface InputConfig {
  rtl: boolean;
  repeat: { initialDelayMs: number; repeatEveryMs: number };
  deadzone: number;
  keyMap: Record<string, import('./actions').InputAction | undefined>;
  gamepad: {
    axesThreshold: number;
    axisToAction: {
      x: { neg: import('./actions').InputAction; pos: import('./actions').InputAction };
      y: { neg: import('./actions').InputAction; pos: import('./actions').InputAction };
    };
  buttons: Record<number, import('./actions').InputAction | undefined>;
  };
}

import type { InputAction } from './actions';

export const defaultInputConfig: InputConfig = {
  rtl: false,
  repeat: { initialDelayMs: 350, repeatEveryMs: 120 },
  deadzone: 0.2,
  keyMap: {
    ArrowUp: 'moveUp',
    ArrowDown: 'moveDown',
    ArrowLeft: 'moveLeft',
    ArrowRight: 'moveRight',
    Enter: 'confirm',
    ' ': 'confirm',
    // Escape: 'back',
    Backspace: 'back',
    Tab: undefined,
  },
  gamepad: {
    axesThreshold: 0.5,
    axisToAction: {
      x: { neg: 'moveLeft' as InputAction, pos: 'moveRight' as InputAction },
      y: { neg: 'moveUp' as InputAction, pos: 'moveDown' as InputAction },
    },
    buttons: {
      0: 'confirm',
      1: 'back',
      8: 'back',
      9: 'menu',
    },
  },
};
