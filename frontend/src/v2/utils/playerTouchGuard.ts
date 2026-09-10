// EmulatorJS never preventDefault()s touches on the virtual gamepad's empty
// zones; the synthesized mouse events then open its menu (EmulatorJS#1221).
const VIRTUAL_GAMEPAD_ZONE_SELECTOR = [
  ".ejs_virtualGamepad_parent",
  ".ejs_virtualGamepad_top",
  ".ejs_virtualGamepad_bottom",
  ".ejs_virtualGamepad_left",
  ".ejs_virtualGamepad_right",
].join(", ");

/** Cancels a touch on an empty virtual-gamepad zone so the browser never
 *  synthesizes the mouse events that would open the EmulatorJS menu. */
export function suppressVirtualGamepadZoneTouch(event: Event): void {
  const target = event.target;
  if (
    target instanceof Element &&
    target.matches(VIRTUAL_GAMEPAD_ZONE_SELECTOR)
  ) {
    event.preventDefault();
  }
}
