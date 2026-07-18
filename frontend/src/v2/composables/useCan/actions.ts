// Permission vocabulary for v2.
//
// `ActionKey` is generated from the backend OpenAPI schema (the source of
// truth) — the catalogue of permission-gated actions, named `domain.action`
// (rom.upload, rom.delete, library.scan, user.create, app.admin, …). The
// scope and grant shapes below are frontend-local: `PermissionScope` is a
// discriminated union (tighter than the generated optional-field schema) so
// `useCan`'s scope matching is exhaustive.
import type { ActionKey } from "@/__generated__";

export type { ActionKey };

export type PermissionScope =
  | { kind: "global" }
  | { kind: "platform"; id: number }
  | { kind: "collection"; id: number }
  | { kind: "rom"; id: number };

export type Grant = {
  action: ActionKey;
  scope: PermissionScope;
};
