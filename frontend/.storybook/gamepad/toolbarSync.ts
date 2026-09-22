/**
 * Single source of truth for toolbar captions and global → boolean parsing.
 *
 * Used by:
 * - GamepadStoryHost (emit label on toggle),
 * - manager.ts (apply label on GLOBALS_UPDATED and filter stale preview events),
 * - unit tests in frontend/test/storybookGamepad.test.ts.
 *
 * shouldApplyPreviewToolbarLabel prevents a race where the preview emits "On" after the user
 * switched Off in the manager (Storybook re-fires the last channel payload).
 */
import { GAMEPAD_GLOBAL_KEY, GAMEPAD_TOOLBAR_EMOJI } from "./constants";

export function fallbackGamepadToolbarLabel(enabled: boolean): string {
  return enabled
    ? `${GAMEPAD_TOOLBAR_EMOJI} Gamepad: On`
    : `${GAMEPAD_TOOLBAR_EMOJI} Gamepad: Off`;
}

export function isGamepadGlobalEnabled(
  globals: Record<string, unknown> | undefined,
): boolean {
  const value = globals?.[GAMEPAD_GLOBAL_KEY];
  if (value === true || value === "true") return true;
  if (value === false || value === "false" || value === "!true") return false;
  return false;
}

/** Drop preview captions that disagree with the gamepadInput global. */
export function shouldApplyPreviewToolbarLabel(
  globals: Record<string, unknown> | undefined,
  label: string,
): boolean {
  const enabled = isGamepadGlobalEnabled(globals);
  if (enabled && label.includes("Gamepad: Off")) return false;
  if (!enabled && label.includes("Gamepad: On")) return false;
  return label === fallbackGamepadToolbarLabel(enabled);
}

export function resolveToolbarLabelOnGlobalsUpdate(
  globals: Record<string, unknown> | undefined,
): string {
  return fallbackGamepadToolbarLabel(isGamepadGlobalEnabled(globals));
}
