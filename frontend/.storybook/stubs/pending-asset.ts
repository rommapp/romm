// Storybook-only: IndexedDB pending-asset store never opens.

export type PendingAssetKind = "save" | "state";

export function pendingAssetId(_romId: number): string {
  return "";
}

export async function pendingAssetKinds(
  _romId: number,
): Promise<Set<PendingAssetKind>> {
  return new Set();
}

export async function syncPendingAssets(): Promise<{
  synced: unknown[];
  dropped: unknown[];
}> {
  return { synced: [], dropped: [] };
}

export async function hasPendingAssets(): Promise<boolean> {
  return false;
}

export default {
  async write() {
    return false;
  },
  async clear() {},
};
