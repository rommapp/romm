// What the EmulatorJS launch view carries across the reload that isolates the
// document (see useIsolatedLaunch). The core and the disc are remembered per
// game already, so only the rest travels.
import { isSlotChoice, type SlotChoice } from "@/v2/utils/saveSlots";

export interface LaunchIntent {
  saveId: number | null;
  stateId: number | null;
  firmwareId: number | null;
  slot: SlotChoice;
  customSlot: string;
}

function isOptionalId(value: unknown): value is number | null {
  return value === null || typeof value === "number";
}

export function isLaunchIntent(value: unknown): value is LaunchIntent {
  return (
    typeof value === "object" &&
    value !== null &&
    "saveId" in value &&
    isOptionalId(value.saveId) &&
    "stateId" in value &&
    isOptionalId(value.stateId) &&
    "firmwareId" in value &&
    isOptionalId(value.firmwareId) &&
    "slot" in value &&
    isSlotChoice(value.slot) &&
    "customSlot" in value &&
    typeof value.customSlot === "string"
  );
}
