import type { SaveSchema, StateSchema } from "@/__generated__";
import { newest } from "@/v2/utils/assets";

// What the player boots from and where progress is written back. A state
// restores the whole machine, SRAM included, so it wins a tie at boot.
export interface ResumeSelection {
  save: SaveSchema | null;
  state: StateSchema | null;
}

export type NewerAsset =
  { kind: "save"; asset: SaveSchema } | { kind: "state"; asset: StateSchema };

/** The latest progress of either kind; a state wins a tie. */
function newestOfEither(
  saves: readonly SaveSchema[],
  compatibleStates: readonly StateSchema[],
): NewerAsset | null {
  const save = newest(saves);
  const state = newest(compatibleStates);
  if (state && (!save || state.updated_at >= save.updated_at)) {
    return { kind: "state", asset: state };
  }
  return save && { kind: "save", asset: save };
}

/** The newest save or compatible state, whichever is later; never both. */
export function defaultResumeSelection(
  saves: readonly SaveSchema[],
  compatibleStates: readonly StateSchema[],
): ResumeSelection {
  const latest = newestOfEither(saves, compatibleStates);
  if (!latest) return { save: null, state: null };
  return latest.kind === "state"
    ? pickState(latest.asset)
    : pickSave(latest.asset);
}

/** A picked save is the boot source, so any armed state is disarmed. */
export function pickSave(save: SaveSchema): ResumeSelection {
  return { save, state: null };
}

/** A picked state carries its own SRAM, so no save stays picked. */
export function pickState(state: StateSchema): ResumeSelection {
  return { save: null, state };
}

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
  const candidate = newestOfEither(saves, compatibleStates);
  return candidate && candidate.asset.updated_at > picked.updated_at
    ? candidate
    : null;
}
