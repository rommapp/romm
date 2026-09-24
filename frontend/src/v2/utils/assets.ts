import type {
  SaveSchema,
  StateSchema,
  UserSaveSchema,
  UserStateSchema,
} from "@/__generated__";

export type AssetType = "save" | "state";
export type Asset = SaveSchema | StateSchema | UserSaveSchema | UserStateSchema;
export type AssetOwner = UserSaveSchema | UserStateSchema;
/** Which of an asset's two timestamps a list or preview reads. */
export type AssetDateField = "updated" | "created";

/** A rehash moves updated_at, so a list ordered on created_at must date by it. */
export function dateOf(asset: Asset, field: AssetDateField): string {
  return field === "created" ? asset.created_at : asset.updated_at;
}

export function ownerOf(asset: Asset): AssetOwner | null {
  return "username" in asset && asset.username ? asset : null;
}

export function screenshotOf(asset: Asset): string | null {
  return asset.screenshot?.download_path ?? null;
}

/** A state loads only in the core that wrote it; one naming no core is anyone's. */
export function isCoreCompatible(
  asset: { emulator?: string | null },
  core: string | null | undefined,
): boolean {
  return !asset.emulator || asset.emulator === core;
}

/** ISO timestamps sort lexically. */
export function byUpdatedDesc(a: Asset, b: Asset): number {
  return b.updated_at.localeCompare(a.updated_at);
}

/**
 * Favorites lead their band, so a run worth keeping outlives its recency.
 * Partitions only: a stable sort keeps the band's own order inside each half.
 */
export function byFavoriteFirst(a: Asset, b: Asset): number {
  return Number(b.is_favorite ?? false) - Number(a.is_favorite ?? false);
}

export function newest<T extends { updated_at: string }>(
  items: readonly T[],
): T | null {
  return items.reduce<T | null>(
    (best, item) => (!best || item.updated_at > best.updated_at ? item : best),
    null,
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
