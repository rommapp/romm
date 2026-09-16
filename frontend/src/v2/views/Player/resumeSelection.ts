import type { SaveSchema, StateSchema } from "@/__generated__";
import { AUTOSAVE_SLOT } from "@/services/api/save";

// What the player boots from and where progress is written back. A state
// restores the whole machine, SRAM included, so it wins at boot.
export interface ResumeSelection {
  save: SaveSchema | null;
  state: StateSchema | null;
}

// With a state armed the save only names the slot new versions go to, so a
// slot-less (archival) save has nothing to contribute.
function writeTarget(save: SaveSchema | null): SaveSchema | null {
  return save?.slot ? save : null;
}

/**
 * Newest compatible state, plus a save only when the write-back choice is
 * unambiguous: with several saves and a state armed the slot stays unpicked.
 */
export function defaultResumeSelection(
  saves: readonly SaveSchema[],
  compatibleStates: readonly StateSchema[],
): ResumeSelection {
  const state = compatibleStates[0] ?? null;
  const save = saves[0] ?? null;
  if (!state) return { save, state };
  return { save: saves.length === 1 ? writeTarget(save) : null, state };
}

/** A picked save is the boot source, so any armed state is disarmed. */
export function pickSave(save: SaveSchema): ResumeSelection {
  return { save, state: null };
}

/** A picked state boots first; a slotted bound save stays as the write target. */
export function pickState(
  selection: ResumeSelection,
  state: StateSchema,
): ResumeSelection {
  return { save: writeTarget(selection.save), state };
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
export function slotChoices(saves: readonly SaveSchema[]): SlotChoice[] {
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

/** The newest save when it postdates the armed state, so the user can be warned. */
export function newerSaveThanState(
  saves: readonly SaveSchema[],
  state: StateSchema,
): SaveSchema | null {
  const newest = saves.reduce<SaveSchema | null>(
    (best, save) => (!best || save.updated_at > best.updated_at ? save : best),
    null,
  );
  return newest && newest.updated_at > state.updated_at ? newest : null;
}
