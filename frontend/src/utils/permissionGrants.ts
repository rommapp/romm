import type { PermEntity } from "@/__generated__";

/**
 * Drops `own_only` on entities with no owner, which the server rejects but
 * stored rows can still carry.
 */
export function clearOwnerlessOwnOnly<
  T extends { entity: PermEntity; own_only?: boolean },
>(items: T[], ownableEntities: readonly PermEntity[]): T[] {
  return items.map((item) =>
    item.own_only && !ownableEntities.includes(item.entity)
      ? { ...item, own_only: false }
      : item,
  );
}
