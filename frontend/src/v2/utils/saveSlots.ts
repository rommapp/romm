import type { SaveSchema } from "@/__generated__";
import { AUTOSAVE_SLOT } from "@/services/api/save";

/** The slot of the newest slotted save, where progress should keep going. */
export function preferredSlot(
  saves: readonly Pick<SaveSchema, "slot">[],
): string {
  return saves.find((save) => save.slot)?.slot ?? AUTOSAVE_SLOT;
}

// Where the session files new saves: a slot already in use, or one the user
// names inline.
export type SlotChoice = { kind: "existing"; slot: string } | { kind: "new" };

export const NEW_SLOT_CHOICE: SlotChoice = { kind: "new" };

export function existingSlot(slot: string): SlotChoice {
  return { kind: "existing", slot };
}

export function isSlotChoice(value: unknown): value is SlotChoice {
  return (
    typeof value === "object" &&
    value !== null &&
    "kind" in value &&
    (value.kind === "existing" || value.kind === "new")
  );
}

/** Autosave first, then every slot in use, then the entry for a new slot. */
export function slotChoices(
  saves: readonly Pick<SaveSchema, "slot">[],
): SlotChoice[] {
  const named = saves
    .map((save) => save.slot)
    .filter((slot): slot is string => !!slot && slot !== AUTOSAVE_SLOT);
  return [
    ...[AUTOSAVE_SLOT, ...new Set(named)].map(existingSlot),
    NEW_SLOT_CHOICE,
  ];
}

/** Identity for select matching: no slot name can collide with the new entry. */
export function slotChoiceKey(choice: SlotChoice): string {
  return choice.kind === "new" ? "new" : `slot:${choice.slot}`;
}

/** The slot a choice resolves to; an unnamed new slot falls back to autosave. */
export function chosenSlot(choice: SlotChoice, newSlotName: string): string {
  if (choice.kind === "existing") return choice.slot;
  return newSlotName.trim() || AUTOSAVE_SLOT;
}
