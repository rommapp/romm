// Live snapshot of a Gamepad sampled by ControllerDebug's RAF loop.
// Mirrors the W3C Gamepad shape, frozen into a plain object that survives
// the next frame (the raw `Gamepad` references can be GC'd between polls).
export interface GamepadSnapshot {
  key: string;
  index: number;
  id: string;
  mapping: string;
  connected: boolean;
  buttons: { pressed: boolean; value: number }[];
  axes: number[];
}
