import type {
  GrantSchemaIO,
  OverrideSchemaIO,
  PermAction,
  PermEntity,
} from "@/__generated__";

export type GrantEffect = "none" | "full" | "own";

export function canOwn(
  entity: PermEntity,
  ownableEntities: readonly PermEntity[],
): boolean {
  return ownableEntities.includes(entity);
}

/**
 * What a granted row allows. The server reads `own_only` on an entity with no
 * owner through the coarse scope alone: full for read/write, nothing for
 * delete, which has no scope.
 */
export function grantEffect(
  grant: { entity: PermEntity; action: PermAction; own_only?: boolean },
  ownableEntities: readonly PermEntity[],
): GrantEffect {
  if (!grant.own_only) return "full";
  if (canOwn(grant.entity, ownableEntities)) return "own";
  return grant.action === "delete" ? "none" : "full";
}

/**
 * Rewrites owner-less `own_only` grants, which the server rejects but stored
 * rows can still carry, into the access they already give.
 */
export function normalizeOwnerlessGrants(
  grants: GrantSchemaIO[],
  ownableEntities: readonly PermEntity[],
): GrantSchemaIO[] {
  return grants.flatMap((g) => {
    const effect = grantEffect(g, ownableEntities);
    return effect === "none" ? [] : [{ ...g, own_only: effect === "own" }];
  });
}

/**
 * Same as `normalizeOwnerlessGrants` for overrides, where an override that
 * allows nothing becomes a revoke so the group's grant can't take its place.
 */
export function normalizeOwnerlessOverrides(
  overrides: OverrideSchemaIO[],
  ownableEntities: readonly PermEntity[],
): OverrideSchemaIO[] {
  return overrides.map((o) => {
    if (!o.own_only || canOwn(o.entity, ownableEntities)) return o;
    const allowsNothing =
      !o.granted || grantEffect(o, ownableEntities) === "none";
    return { ...o, granted: !allowsNothing, own_only: false };
  });
}
