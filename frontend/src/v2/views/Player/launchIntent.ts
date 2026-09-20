// What the EmulatorJS launch view carries across the reload that isolates the
// document (see useIsolatedLaunch). Only ids travel, so they are resolved again
// against what the server offers; the core and the disc persist per game.
import type { FirmwareSchema, SaveSchema, StateSchema } from "@/__generated__";
import { isSlotChoice, type SlotChoice } from "@/v2/utils/saveSlots";
import type { ResumeSelection } from "./resumeSelection";

/** The pre-play selection a reload has to preserve. */
export interface LaunchSelection {
  resume: ResumeSelection;
  firmware: FirmwareSchema | null;
  slot: SlotChoice;
  customSlot: string;
}

/** That selection as ids, which is all a stored intent can hold. */
export interface LaunchIntent {
  saveId: number | null;
  stateId: number | null;
  firmwareId: number | null;
  slot: SlotChoice;
  customSlot: string;
}

/** What the view offers to pick from, on the other side of the reload. */
export interface LaunchOptions {
  saves: readonly SaveSchema[];
  states: readonly StateSchema[];
  firmware: readonly FirmwareSchema[];
}

export function launchIntentFor(selection: LaunchSelection): LaunchIntent {
  return {
    saveId: selection.resume.save?.id ?? null,
    stateId: selection.resume.state?.id ?? null,
    firmwareId: selection.firmware?.id ?? null,
    slot: selection.slot,
    customSlot: selection.customSlot,
  };
}

/** The selection an intent names, dropping whatever is no longer offered. */
export function resolveLaunchIntent(
  intent: LaunchIntent,
  options: LaunchOptions,
): LaunchSelection {
  return {
    resume: {
      save: byId(options.saves, intent.saveId),
      state: byId(options.states, intent.stateId),
    },
    firmware: byId(options.firmware, intent.firmwareId),
    slot: intent.slot,
    customSlot: intent.customSlot,
  };
}

function byId<T extends { id: number }>(
  items: readonly T[],
  id: number | null,
): T | null {
  return items.find((item) => item.id === id) ?? null;
}

const ID_KEYS = ["saveId", "stateId", "firmwareId"] as const;

function hasOptionalId(value: object, key: string): boolean {
  if (!(key in value)) return false;
  const id = (value as Record<string, unknown>)[key];
  return id === null || typeof id === "number";
}

export function isLaunchIntent(value: unknown): value is LaunchIntent {
  return (
    typeof value === "object" &&
    value !== null &&
    ID_KEYS.every((key) => hasOptionalId(value, key)) &&
    "slot" in value &&
    isSlotChoice(value.slot) &&
    "customSlot" in value &&
    typeof value.customSlot === "string"
  );
}
