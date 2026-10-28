import type { SaveSchema } from "@/__generated__";
import i18n from "@/locales";
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

/** The entry for a new slot first, then autosave and every slot in use. */
export function slotChoices(
  saves: readonly Pick<SaveSchema, "slot">[],
): SlotChoice[] {
  const named = saves
    .map((save) => save.slot)
    .filter((slot): slot is string => !!slot && slot !== AUTOSAVE_SLOT);
  return [
    NEW_SLOT_CHOICE,
    ...[AUTOSAVE_SLOT, ...new Set(named)].map(existingSlot),
  ];
}

/** Pickers set the new-slot entry apart from the slots that already exist. */
export function isNewSlotChoice(choice: { kind: string }): boolean {
  return choice.kind === "new";
}

export function slotChoiceTitle(choice: SlotChoice): string {
  return choice.kind === "new" ? i18n.global.t("play.new-slot") : choice.slot;
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

/** A slotted save fixes the write slot; an archive leaves the choice as is. */
export function slotForSave(
  save: Pick<SaveSchema, "slot">,
  current: SlotChoice,
): SlotChoice {
  return save.slot ? existingSlot(save.slot) : current;
}
