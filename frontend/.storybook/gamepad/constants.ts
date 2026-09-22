/**
 * Shared identifiers for the Storybook gamepad POC.
 *
 * Data path (high level):
 *   preview.ts globalTypes[GAMEPAD_GLOBAL_KEY]  →  toolbar toggle in the manager UI
 *   withGamepad.ts reads that global  →  GamepadStoryHost :enabled
 *   GamepadStoryHost  →  GamepadInputLayer (RomM useGamepad) + StorybookGamepadStatus (canvas HUD)
 *   GamepadStoryHost emits GAMEPAD_TOOLBAR_LABEL_EVENT  →  manager.ts patches the toolbar button text
 */
/** Must match preview.ts `globalTypes` key and Storybook's generated control id (`gamepadInput`). */
export const GAMEPAD_GLOBAL_KEY = "gamepadInput";

export const GAMEPAD_TOOLBAR_EMOJI = "🎮";

export const ACTIVITY_HOLD_MS = 150;

/** Recent-event subline visibility in the canvas status panel. */
export const RECENT_EVENT_FADE_MS = 5000;

export const MAX_PAD_LABEL_LEN = 36;

/** Preview → manager: full toolbar caption (`Gamepad: …`). */
export const GAMEPAD_TOOLBAR_LABEL_EVENT =
  "romm/storybook-gamepad/toolbar-label";
