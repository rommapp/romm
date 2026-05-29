// ActionKey — canonical vocabulary of permission-gated actions in v2.
//
// This list is authored by hand today. It mirrors the backend's permission
// guards by convention. When the backend exposes its action catalog in
// OpenAPI (debt — see CLAUDE.md), this file is replaced by a generated
// type and the manual review checklist disappears.
//
// Naming convention: `domain.action`. Domains are nouns (rom, platform,
// collection, user, library); actions are verbs (view, create, edit,
// delete, upload, scan, …).

export const ACTIONS = [
  // ROMs
  "rom.view",
  "rom.play",
  "rom.download",
  "rom.upload",
  "rom.edit",
  "rom.delete",
  "rom.match",
  "rom.refresh",
  "rom.favorite",
  // Platforms
  "platform.view",
  "platform.create",
  "platform.edit",
  "platform.delete",
  // Collections
  "collection.view",
  "collection.create",
  "collection.edit",
  "collection.delete",
  // Library
  "library.scan",
  // Users
  "user.view",
  "user.create",
  "user.edit",
  "user.delete",
  // App-wide — generic "is admin" hatch for surfaces that don't map to a
  // specific resource action (server stats, About, debug panels). Prefer
  // a more specific action when one fits.
  "app.admin",
] as const;

export type ActionKey = (typeof ACTIONS)[number];

export type PermissionScope =
  | { kind: "global" }
  | { kind: "platform"; id: number }
  | { kind: "collection"; id: number }
  | { kind: "rom"; id: number };

export type Grant = {
  action: ActionKey;
  scope: PermissionScope;
};
