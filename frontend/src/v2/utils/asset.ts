import type {
  SaveSchema,
  StateSchema,
  UserSaveSchema,
  UserStateSchema,
} from "@/__generated__";

/** A save or state, in either its plain or owner-enriched (community) form. */
export type Asset = SaveSchema | StateSchema | UserSaveSchema | UserStateSchema;

export type AssetType = "save" | "state";

// Saves carry a capture as readily as states do: the two `screenshot` lookups
// are identical on the model, and the player uploads one captured frame with
// both. So nothing here keys off the asset type.
export function assetScreenshotUrl(asset: Asset): string | null {
  return asset.screenshot?.download_path ?? null;
}

// Whether a whole list has anything to show in a capture slot. Decided across
// the list so rows without a capture stay aligned with the ones that have one.
export function anyAssetHasScreenshot(assets: readonly Asset[]): boolean {
  return assets.some((asset) => assetScreenshotUrl(asset) !== null);
}

/** Stand-in for a missing capture. */
export function assetFallbackIcon(type: AssetType): string {
  return type === "save" ? "mdi-content-save" : "mdi-file-outline";
}
