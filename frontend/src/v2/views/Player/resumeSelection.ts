import type { SaveSchema, StateSchema } from "@/__generated__";

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
  const candidates: NewerAsset[] = [
    ...saves.map((asset) => ({ kind: "save", asset }) as const),
    ...compatibleStates.map((asset) => ({ kind: "state", asset }) as const),
  ];
  const newest = candidates.reduce<NewerAsset | null>(
    (best, candidate) =>
      !best || candidate.asset.updated_at > best.asset.updated_at
        ? candidate
        : best,
    null,
  );
  return newest && newest.asset.updated_at > picked.updated_at ? newest : null;
}
