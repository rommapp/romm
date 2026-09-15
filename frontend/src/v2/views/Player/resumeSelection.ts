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

/** Slots a new save can go to: autosave first, then every slot in use. */
export function slotOptions(saves: readonly SaveSchema[]): string[] {
  const named = saves
    .map((save) => save.slot)
    .filter((slot): slot is string => !!slot && slot !== AUTOSAVE_SLOT);
  return [AUTOSAVE_SLOT, ...new Set(named)];
}
