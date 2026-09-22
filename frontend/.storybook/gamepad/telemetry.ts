/**
 * Preview-only gamepad polling helpers for the canvas status bar.
 *
 * Reuses isUsablePad / PAD_BUTTON / AXIS_THRESHOLD from v2 useGamepad so "connected" and
 * button names match production. Consumed only by GamepadStoryHost → StorybookGamepadStatus.
 * Not sent to the manager toolbar (toolbar stays Off/On).
 */
import {
  AXIS_THRESHOLD,
  isUsablePad,
  PAD_BUTTON,
} from "@/v2/composables/useGamepad";
import { ACTIVITY_HOLD_MS, RECENT_EVENT_FADE_MS } from "./constants";

export type ActivityBucket = "dpad" | "stick" | "face" | "menu";

export type ActivityLights = Record<ActivityBucket, boolean>;

export interface GamepadTelemetryPayload {
  enabled: boolean;
  connected: boolean;
  padLabel: string | null;
  padIndex: number | null;
  activity: ActivityLights;
  recentEvent: string | null;
  /** Bumps on each new event so the subline fade animation restarts. */
  recentEventSeq: number;
}

const DPAD_INDICES = new Set([12, 13, 14, 15]);
const FACE_INDICES = new Set([0, 1, 2, 3]);
const MENU_INDICES = new Set([4, 5, 8, 9]);

const BUTTON_EVENT_LABEL: Record<number, string> = Object.fromEntries(
  Object.entries(PAD_BUTTON).map(([name, index]) => [
    index,
    name.replace(/-/g, " "),
  ]),
);

export function truncatePadLabel(id: string, maxLen: number): string {
  const trimmed = id.trim();
  if (trimmed.length <= maxLen) return trimmed;
  return `${trimmed.slice(0, maxLen - 1)}…`;
}

export function findFirstUsablePad(): Gamepad | null {
  if (typeof navigator === "undefined" || !navigator.getGamepads) {
    return null;
  }
  try {
    const list = navigator.getGamepads();
    for (const pad of list) {
      if (isUsablePad(pad)) return pad;
    }
  } catch {
    return null;
  }
  return null;
}

function readInstantActivity(pad: Gamepad): ActivityLights {
  const activity: ActivityLights = {
    dpad: false,
    stick: false,
    face: false,
    menu: false,
  };

  for (let i = 0; i < pad.buttons.length; i++) {
    const button = pad.buttons[i];
    if (!button?.pressed && (button?.value ?? 0) <= 0.05) continue;
    if (DPAD_INDICES.has(i)) activity.dpad = true;
    else if (FACE_INDICES.has(i)) activity.face = true;
    else if (MENU_INDICES.has(i)) activity.menu = true;
  }

  const x = pad.axes[0] ?? 0;
  const y = pad.axes[1] ?? 0;
  if (Math.abs(x) >= AXIS_THRESHOLD || Math.abs(y) >= AXIS_THRESHOLD) {
    activity.stick = true;
  }

  return activity;
}

function isPressed(button: GamepadButton | undefined): boolean {
  if (!button) return false;
  return button.pressed || button.value > 0.05;
}

function stickEnterLabel(
  prevX: number,
  prevY: number,
  x: number,
  y: number,
): string | null {
  const prevActive =
    Math.abs(prevX) >= AXIS_THRESHOLD || Math.abs(prevY) >= AXIS_THRESHOLD;
  const active = Math.abs(x) >= AXIS_THRESHOLD || Math.abs(y) >= AXIS_THRESHOLD;
  if (!active || prevActive) return null;

  if (Math.abs(x) >= Math.abs(y)) {
    return x > 0 ? "Left stick right" : "Left stick left";
  }
  return y > 0 ? "Left stick down" : "Left stick up";
}

export function createActivityTracker() {
  const until: Record<ActivityBucket, number> = {
    dpad: 0,
    stick: 0,
    face: 0,
    menu: 0,
  };

  let prevPressed: boolean[] = [];
  let prevStickX = 0;
  let prevStickY = 0;
  let recentEvent: string | null = null;
  let recentEventSeq = 0;
  let recentEventUntil = 0;

  function logEvent(label: string, now: number) {
    recentEvent = label;
    recentEventSeq += 1;
    recentEventUntil = now + RECENT_EVENT_FADE_MS;
  }

  function detectEvents(pad: Gamepad, now: number) {
    if (now > recentEventUntil) recentEvent = null;

    for (let i = 0; i < pad.buttons.length; i++) {
      const pressed = isPressed(pad.buttons[i]);
      const was = prevPressed[i] ?? false;
      if (pressed && !was) {
        const label = BUTTON_EVENT_LABEL[i] ?? `Button ${i}`;
        logEvent(label, now);
      }
      prevPressed[i] = pressed;
    }

    const x = pad.axes[0] ?? 0;
    const y = pad.axes[1] ?? 0;
    const stickLabel = stickEnterLabel(prevStickX, prevStickY, x, y);
    if (stickLabel) logEvent(stickLabel, now);
    prevStickX = x;
    prevStickY = y;
  }

  function tick(pad: Gamepad | null, now: number): ActivityLights {
    if (pad) detectEvents(pad, now);
    else if (now > recentEventUntil) recentEvent = null;

    const instant = pad ? readInstantActivity(pad) : null;
    const buckets: ActivityBucket[] = ["dpad", "stick", "face", "menu"];
    for (const key of buckets) {
      if (instant?.[key]) until[key] = now + ACTIVITY_HOLD_MS;
    }
    return {
      dpad: now < until.dpad,
      stick: now < until.stick,
      face: now < until.face,
      menu: now < until.menu,
    };
  }

  function getRecentEvent() {
    return { recentEvent, recentEventSeq };
  }

  function reset() {
    until.dpad = 0;
    until.stick = 0;
    until.face = 0;
    until.menu = 0;
    prevPressed = [];
    prevStickX = 0;
    prevStickY = 0;
    recentEvent = null;
    recentEventSeq = 0;
    recentEventUntil = 0;
  }

  return { tick, reset, getRecentEvent };
}

export function buildTelemetryPayload(
  enabled: boolean,
  pad: Gamepad | null,
  activity: ActivityLights,
  recent: { recentEvent: string | null; recentEventSeq: number },
  maxLabelLen: number,
): GamepadTelemetryPayload {
  return {
    enabled,
    connected: pad !== null,
    padLabel: pad ? truncatePadLabel(pad.id, maxLabelLen) : null,
    padIndex: pad?.index ?? null,
    activity,
    recentEvent: recent.recentEvent,
    recentEventSeq: recent.recentEventSeq,
  };
}
