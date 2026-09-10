import type {
  SaveSchema,
  StateSchema,
  UserSaveSchema,
  UserStateSchema,
} from "@/__generated__";

/** A save or state, in either its plain or owner-enriched (community) form. */
export type Asset = SaveSchema | StateSchema | UserSaveSchema | UserStateSchema;

// Saves carry a capture as readily as states do: the two `screenshot` lookups
// are identical on the model, and the player uploads one captured frame with
// both. Callers that still gate this on the asset type are tracked in #4422.
export function assetScreenshotUrl(asset: Asset): string | null {
  return asset.screenshot?.download_path ?? null;
}
