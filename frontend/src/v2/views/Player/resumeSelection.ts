import type { SaveSchema, StateSchema } from "@/__generated__";
import { newest } from "@/v2/utils/assets";

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

/** A picked state carries its own SRAM, so no save stays picked. */
export function pickState(state: StateSchema): ResumeSelection {
  return { save: null, state };
}

export type NewerAsset =
  { kind: "save"; asset: SaveSchema } | { kind: "state"; asset: StateSchema };

/**
 * The newest save or compatible state when it postdates what boots, so the
 * user can be warned before older progress rolls the newer back.
 */
export function newerThanPick(
  saves: readonly SaveSchema[],
  compatibleStates: readonly StateSchema[],
  selection: ResumeSelection,
): NewerAsset | null {
  const picked = selection.state ?? selection.save;
  if (!picked) return null;
  const save = newest(saves);
  const state = newest(compatibleStates);
  const candidate: NewerAsset | null =
    state && (!save || state.updated_at > save.updated_at)
      ? { kind: "state", asset: state }
      : save && { kind: "save", asset: save };
  return candidate && candidate.asset.updated_at > picked.updated_at
    ? candidate
    : null;
}
