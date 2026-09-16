import type {
  SaveSchema,
  StateSchema,
  UserSaveSchema,
  UserStateSchema,
} from "@/__generated__";

export type AssetType = "save" | "state";
export type Asset = SaveSchema | StateSchema | UserSaveSchema | UserStateSchema;
export type AssetOwner = UserSaveSchema | UserStateSchema;

export function ownerOf(asset: Asset): AssetOwner | null {
  return "username" in asset && asset.username ? asset : null;
}

export function screenshotOf(asset: Asset): string | null {
  return asset.screenshot?.download_path ?? null;
}

/** ISO timestamps sort lexically. */
export function byUpdatedDesc(a: Asset, b: Asset): number {
  return b.updated_at.localeCompare(a.updated_at);
}

export function newestUpdatedAt(assets: readonly Asset[]): string {
  return assets.reduce(
    (best, asset) => (asset.updated_at > best ? asset.updated_at : best),
    "",
  );
}

/** Entrance-stagger index per rendered asset, continuous across groups. */
export function staggerIndex(
  visibleGroups: readonly (readonly Asset[])[],
): Map<number, number> {
  const order = new Map<number, number>();
  for (const assets of visibleGroups) {
    for (const asset of assets) order.set(asset.id, order.size);
  }
  return order;
}
