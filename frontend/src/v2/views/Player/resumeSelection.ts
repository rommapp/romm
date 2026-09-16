import type { SaveSchema, StateSchema } from "@/__generated__";
import { AUTOSAVE_SLOT } from "@/services/api/save";

// What the player boots from and where progress is written back. A state
// restores the whole machine, SRAM included, so it wins at boot.
export interface ResumeSelection {
  save: SaveSchema | null;
  state: StateSchema | null;
}

/** The newest compatible state, else the newest save; never both. */
export function defaultResumeSelection(
  saves: readonly SaveSchema[],
  compatibleStates: readonly StateSchema[],
): ResumeSelection {
  const state = compatibleStates[0] ?? null;
  return { save: state ? null : (saves[0] ?? null), state };
}

/** A picked save is the boot source, so any armed state is disarmed. */
export function pickSave(save: SaveSchema): ResumeSelection {
  return { save, state: null };
}

/** A picked state carries its own SRAM, so no save stays bound. */
export function pickState(state: StateSchema): ResumeSelection {
  return { save: null, state };
}

/** The slot of the newest slotted save, where progress should keep going. */
export function preferredSlot(saves: readonly SaveSchema[]): string {
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
