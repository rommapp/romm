import type { SaveSchema, StateSchema } from "@/__generated__";
import { newest } from "@/utils/assets";

// What the player boots from and where progress is written back. A state
// restores the whole machine, SRAM included, so it wins a tie at boot unless
// another device wrote the save (see defaultResumeSelection).
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

// Server timestamps of a save and a state uploaded together by one quit.
const SAME_QUIT_WINDOW_MS = 5_000;

function writtenTogether(save: SaveSchema, state: StateSchema): boolean {
  const gap = Date.parse(state.updated_at) - Date.parse(save.updated_at);
  return Math.abs(gap) <= SAME_QUIT_WINDOW_MS;
}

/**
 * The newest save or compatible state, whichever is later; never both.
 *
 * Args:
 *   thisDeviceId: this browser's sync device, if it registered one.
 */
export function defaultResumeSelection(
  saves: readonly SaveSchema[],
  compatibleStates: readonly StateSchema[],
  thisDeviceId: string | null = null,
): ResumeSelection {
  const latest = newestOfEither(saves, compatibleStates);
  if (!latest) return { save: null, state: null };
  // States record no device, so one written with another device's save likely
  // came from that device's core, which may not load here.
  const save = newest(saves);
  if (
    latest.kind === "state" &&
    save?.origin_device_id &&
    save.origin_device_id !== thisDeviceId &&
    writtenTogether(save, latest.asset)
  ) {
    return pickSave(save);
  }
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
  if (!candidate || candidate.asset.updated_at <= picked.updated_at)
    return null;
  // A state from the same quit as the picked save holds no newer progress.
  if (
    candidate.kind === "state" &&
    selection.save &&
    writtenTogether(selection.save, candidate.asset)
  ) {
    return null;
  }
  return candidate;
}
