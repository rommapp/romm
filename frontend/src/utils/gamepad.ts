import { isEditable } from "@/utils/editable";

// Firefox keeps disconnected entries in getGamepads(), and their stale axes
// drift across the press threshold with no input (#3851).
export function isUsablePad(pad: Gamepad | null): pad is Gamepad {
  return pad !== null && pad.connected;
}

/** The right stick's strongest deflection on each axis across usable pads. */
export function readRightStick(): { x: number; y: number } {
  let x = 0;
  let y = 0;
  for (const pad of navigator.getGamepads?.() ?? []) {
    if (!isUsablePad(pad)) continue;
    // Standard mapping: right stick is axes 2 (X) and 3 (Y).
    const ax = pad.axes[2] ?? 0;
    const ay = pad.axes[3] ?? 0;
    if (Math.abs(ax) > Math.abs(x)) x = ax;
    if (Math.abs(ay) > Math.abs(y)) y = ay;
  }
  return { x, y };
}

/** An open combobox's aria-activedescendant identifies the option pad A activates. */
export function padActivationTarget(el: Element | null): HTMLElement | null {
  if (!(el instanceof HTMLElement)) return null;
  if (el.getAttribute("aria-expanded") === "true") {
    const id = el.getAttribute("aria-activedescendant");
    const option = id ? document.getElementById(id) : null;
    if (option) return option;
  }
  return isEditable(el) ? null : el;
}
