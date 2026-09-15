import type { SaveSchema, StateSchema } from "@/__generated__";
import { AUTOSAVE_SLOT, isAutosaveSlot } from "@/services/api/save";

// What the player boots from and where progress is written back. A state
// restores the whole machine, SRAM included, so it always wins at boot; the
// save is then only the "Save & Quit" write-back target.
export interface ResumeSelection {
  save: SaveSchema | null;
  state: StateSchema | null;
}

/**
 * Newest compatible state, plus a save only when the write-back choice is
 * unambiguous.
 *
 * With a state armed and several saves, loading the state injects a different
 * SRAM timeline, so auto-binding an arbitrary save would let "Save & Quit"
 * overwrite a slot the user never picked. That case stays unbound until the
 * user picks a save explicitly.
 */
export function defaultResumeSelection(
  saves: readonly SaveSchema[],
  compatibleStates: readonly StateSchema[],
): ResumeSelection {
  const state = compatibleStates[0] ?? null;
  const safeToBindSave = saves.length === 1 || !state;
  return { save: safeToBindSave ? (saves[0] ?? null) : null, state };
}

/** A picked save is the boot source, so any armed state is disarmed. */
export function pickSave(save: SaveSchema): ResumeSelection {
  return { save, state: null };
}

/** A picked state boots first; the bound save stays as the write-back target. */
export function pickState(
  selection: ResumeSelection,
  state: StateSchema,
): ResumeSelection {
  return { save: selection.save, state };
}

/** Slots a new save can go to: autosave first, then every slot in use. */
export function slotOptions(saves: readonly SaveSchema[]): string[] {
  const named = saves
    .map((save) => save.slot)
    .filter((slot): slot is string => !!slot && !isAutosaveSlot(slot));
  return [AUTOSAVE_SLOT, ...new Set(named)];
}
