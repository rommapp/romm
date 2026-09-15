import type {
  SaveSchema,
  StateSchema,
  UserSaveSchema,
  UserStateSchema,
} from "@/__generated__";

/** A save or state, in either its plain or owner-enriched (community) form. */
export type Asset = SaveSchema | StateSchema | UserSaveSchema | UserStateSchema;

export type AssetType = "save" | "state";

/** Everything the asset surfaces key off the type for: the icon standing in
 *  for a missing capture, and the empty-state icon and string. */
export const ASSET_TYPE_META = {
  save: {
    icon: "mdi-content-save",
    emptyIcon: "mdi-content-save-outline",
    emptyLabelKey: "play.no-saves-available",
  },
  state: {
    icon: "mdi-file-outline",
    emptyIcon: "mdi-file-outline",
    emptyLabelKey: "play.no-states-available",
  },
} as const satisfies Record<
  AssetType,
  { icon: string; emptyIcon: string; emptyLabelKey: string }
>;

// Both kinds carry a screenshot: the player uploads one captured frame with
// each, so nothing here keys off the asset type.
export function assetScreenshotUrl(asset: Asset): string | null {
  return asset.screenshot?.download_path ?? null;
}

// Decided across the list so rows whose asset lacks a capture still line up
// with the rows that have one.
export function anyAssetHasScreenshot(assets: readonly Asset[]): boolean {
  return assets.some((asset) => assetScreenshotUrl(asset) !== null);
}

/** The author of a community asset, or null for the viewer's own. */
export function assetOwner(
  asset: Asset,
): UserSaveSchema | UserStateSchema | null {
  return "username" in asset && asset.username ? asset : null;
}
