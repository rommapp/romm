/** Legacy helper: toolbar labels no longer include live telemetry (see GamepadStoryHost). */
import type { GamepadTelemetryPayload } from "./telemetry";
import { fallbackGamepadToolbarLabel } from "./toolbarSync";

/** Toolbar caption: toggle only (details live in the canvas status bar). */
export function formatGamepadToolbarLabel(t: GamepadTelemetryPayload): string {
  return fallbackGamepadToolbarLabel(t.enabled);
}
