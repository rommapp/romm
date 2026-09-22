/** Unit tests for gamepad/toolbarSync.ts (manager ↔ preview label contract). */
import { describe, expect, it } from "vitest";
import { GAMEPAD_GLOBAL_KEY } from "../.storybook/gamepad/constants";
import type { GamepadTelemetryPayload } from "../.storybook/gamepad/telemetry";
import { formatGamepadToolbarLabel } from "../.storybook/gamepad/toolbarStatus";
import {
  fallbackGamepadToolbarLabel,
  isGamepadGlobalEnabled,
  resolveToolbarLabelOnGlobalsUpdate,
  shouldApplyPreviewToolbarLabel,
} from "../.storybook/gamepad/toolbarSync";

function payload(
  overrides: Partial<GamepadTelemetryPayload> = {},
): GamepadTelemetryPayload {
  return {
    enabled: false,
    connected: false,
    padLabel: null,
    padIndex: null,
    activity: { dpad: false, stick: false, face: false, menu: false },
    recentEvent: null,
    recentEventSeq: 0,
    ...overrides,
  };
}

describe("formatGamepadToolbarLabel", () => {
  it("is only Gamepad: Off or Gamepad: On", () => {
    expect(formatGamepadToolbarLabel(payload())).toBe("🎮 Gamepad: Off");
    expect(formatGamepadToolbarLabel(payload({ enabled: true }))).toBe(
      "🎮 Gamepad: On",
    );
  });

  it("ignores connection, pad id, and input activity", () => {
    expect(
      formatGamepadToolbarLabel(
        payload({
          enabled: true,
          connected: true,
          padLabel: "054c-05c4-Wireless Controller",
          activity: { dpad: true, stick: true, face: true, menu: true },
          recentEvent: "a",
        }),
      ),
    ).toBe("🎮 Gamepad: On");
  });
});

describe("resolveToolbarLabelOnGlobalsUpdate", () => {
  it("returns Off when global is false", () => {
    expect(
      resolveToolbarLabelOnGlobalsUpdate(
        { [GAMEPAD_GLOBAL_KEY]: false },
        "🎮 Gamepad: On · anything",
      ),
    ).toBe("🎮 Gamepad: Off");
  });

  it("returns On when global is true", () => {
    expect(
      resolveToolbarLabelOnGlobalsUpdate(
        { [GAMEPAD_GLOBAL_KEY]: true },
        "🎮 Gamepad: Off",
      ),
    ).toBe("🎮 Gamepad: On");
  });
});

describe("isGamepadGlobalEnabled", () => {
  it("accepts boolean and string true", () => {
    expect(isGamepadGlobalEnabled({ [GAMEPAD_GLOBAL_KEY]: true })).toBe(true);
    expect(isGamepadGlobalEnabled({ [GAMEPAD_GLOBAL_KEY]: "true" })).toBe(true);
    expect(isGamepadGlobalEnabled({ [GAMEPAD_GLOBAL_KEY]: false })).toBe(false);
  });
});

describe("shouldApplyPreviewToolbarLabel", () => {
  it("rejects Off caption while global is true", () => {
    expect(
      shouldApplyPreviewToolbarLabel(
        { [GAMEPAD_GLOBAL_KEY]: true },
        "🎮 Gamepad: Off",
      ),
    ).toBe(false);
  });

  it("rejects On caption while global is false", () => {
    expect(
      shouldApplyPreviewToolbarLabel(
        { [GAMEPAD_GLOBAL_KEY]: false },
        "🎮 Gamepad: On",
      ),
    ).toBe(false);
  });

  it("allows only the canonical On label when global is true", () => {
    expect(
      shouldApplyPreviewToolbarLabel(
        { [GAMEPAD_GLOBAL_KEY]: true },
        "🎮 Gamepad: On",
      ),
    ).toBe(true);
    expect(
      shouldApplyPreviewToolbarLabel(
        { [GAMEPAD_GLOBAL_KEY]: true },
        "🎮 Gamepad: On · Input",
      ),
    ).toBe(false);
  });
});

describe("fallbackGamepadToolbarLabel", () => {
  it("matches toolbar menu items", () => {
    expect(fallbackGamepadToolbarLabel(false)).toBe("🎮 Gamepad: Off");
    expect(fallbackGamepadToolbarLabel(true)).toBe("🎮 Gamepad: On");
  });
});
