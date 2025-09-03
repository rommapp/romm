import type { InputAction } from "./actions";
import { InputBus } from "./bus";
import { defaultInputConfig } from "./config";

interface ButtonState {
  pressed: boolean;
  nextRepeatAt: number;
}

export function attachGamepad(bus: InputBus) {
  const states: Record<
    string,
    {
      buttons: Record<number, ButtonState>;
      axesRepeatAt: Record<"x" | "y", number>;
    }
  > = {};
  const now = () => performance.now();

  const onConnect = () => {};
  const onDisconnect = () => {};
  window.addEventListener("gamepadconnected", onConnect);
  window.addEventListener("gamepaddisconnected", onDisconnect);

  let rafId = 0;
  const loop = () => {
    const pads = navigator.getGamepads?.() || [];
    const t = now();
    for (const pad of pads) {
      if (!pad) continue;
      const key = `${pad.index}:${pad.id}`;
      const st = (states[key] ||= {
        buttons: {},
        axesRepeatAt: { x: 0, y: 0 },
      });

      const x = pad.axes[0] || 0;
      const y = pad.axes[1] || 0;
      const thr = defaultInputConfig.gamepad.axesThreshold;
      const delay = defaultInputConfig.repeat.initialDelayMs;
      const rep = defaultInputConfig.repeat.repeatEveryMs;
      const fireAxis = (axis: "x" | "y", v: number) => {
        if (Math.abs(v) < thr) {
          st.axesRepeatAt[axis] = 0;
          return;
        }
        const dirAction: InputAction =
          v < 0
            ? axis === "x"
              ? defaultInputConfig.gamepad.axisToAction.x.neg
              : defaultInputConfig.gamepad.axisToAction.y.neg
            : axis === "x"
              ? defaultInputConfig.gamepad.axisToAction.x.pos
              : defaultInputConfig.gamepad.axisToAction.y.pos;
        if (st.axesRepeatAt[axis] === 0) {
          bus.dispatch(dirAction);
          st.axesRepeatAt[axis] = t + delay;
        } else if (t >= st.axesRepeatAt[axis]) {
          bus.dispatch(dirAction);
          st.axesRepeatAt[axis] = t + rep;
        }
      };
      fireAxis("x", x);
      fireAxis("y", y);

      for (let i = 0; i < pad.buttons.length; i++) {
        const b = pad.buttons[i];
        const action = defaultInputConfig.gamepad.buttons[i];
        if (!action) continue;
        const prev = (st.buttons[i] ||= { pressed: false, nextRepeatAt: 0 });
        if (b.pressed) {
          if (!prev.pressed) {
            bus.dispatch(action);
            prev.pressed = true;
            prev.nextRepeatAt = t + delay;
          } else if (t >= prev.nextRepeatAt) {
            bus.dispatch(action);
            prev.nextRepeatAt = t + rep;
          }
        } else {
          prev.pressed = false;
          prev.nextRepeatAt = 0;
        }
      }
    }
    rafId = requestAnimationFrame(loop);
  };
  rafId = requestAnimationFrame(loop);

  return () => {
    cancelAnimationFrame(rafId);
    window.removeEventListener("gamepadconnected", onConnect);
    window.removeEventListener("gamepaddisconnected", onDisconnect);
  };
}
