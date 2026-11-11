import type { SaveSchema, StateSchema } from "@/__generated__";
import { newest } from "@/utils/assets";

// What the player boots from and where progress is written back. A state
// restores the whole machine, SRAM included, so it wins a tie at boot unless
// another device wrote it (see defaultResumeSelection).
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

// A state another device's core wrote may not load here.
function ownStates(
  compatibleStates: readonly StateSchema[],
  thisDeviceId: string | null,
): StateSchema[] {
  return compatibleStates.filter(
    (state) =>
      !state.origin_device_id || state.origin_device_id === thisDeviceId,
  );
}

/**
 * The newest save or this device's compatible state, whichever is later;
 * never both.
 *
 * Args:
 *   thisDeviceId: this browser's sync device, if it registered one.
 */
export function defaultResumeSelection(
  saves: readonly SaveSchema[],
  compatibleStates: readonly StateSchema[],
  thisDeviceId: string | null = null,
): ResumeSelection {
  const latest = newestOfEither(
    saves,
    ownStates(compatibleStates, thisDeviceId),
  );
  if (latest) {
    return latest.kind === "state"
      ? pickState(latest.asset)
      : pickSave(latest.asset);
  }
  // Another device's state still beats starting from nothing.
  const fallback = newest(compatibleStates);
  return fallback ? pickState(fallback) : { save: null, state: null };
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
 * The newest save or this device's compatible state when it postdates what
 * boots, so the user can be warned before older progress rolls the newer back.
 */
export function newerThanPick(
  saves: readonly SaveSchema[],
  compatibleStates: readonly StateSchema[],
  selection: ResumeSelection,
  thisDeviceId: string | null = null,
): NewerAsset | null {
  const picked = selection.state ?? selection.save;
  if (!picked) return null;
  const candidate = newestOfEither(
    saves,
    ownStates(compatibleStates, thisDeviceId),
  );
  return candidate && candidate.asset.updated_at > picked.updated_at
    ? candidate
    : null;
}
