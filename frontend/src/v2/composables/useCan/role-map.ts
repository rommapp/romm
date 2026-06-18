// role-map — role → set of action keys that the role can perform globally.
//
// This is a TEMPORARY hardcoded mirror of the backend's role-based guards.
// When the backend ships /permissions/me with normalised grants per user,
// this file is deleted and the store hydrates directly from the response.
//
// Review this file against backend guards when changing it. If a backend
// guard changes shape (role allowed/forbidden), update here too. Drift
// between this map and backend means the UI will offer actions the
// server rejects, or hide actions the server would have permitted.
import type { Role } from "@/__generated__";
import type { ActionKey } from "./actions";

const ALL_ROLES: Role[] = ["viewer", "editor", "admin"];
const EDITOR_UP: Role[] = ["editor", "admin"];
const ADMIN_ONLY: Role[] = ["admin"];

const ACTION_ROLES: Record<ActionKey, Role[]> = {
  // ROMs — read access for any role; write access from editor up; delete admin only.
  "rom.view": ALL_ROLES,
  "rom.play": ALL_ROLES,
  "rom.download": ALL_ROLES,
  "rom.favorite": ALL_ROLES,
  "rom.upload": EDITOR_UP,
  "rom.edit": EDITOR_UP,
  "rom.match": EDITOR_UP,
  "rom.refresh": EDITOR_UP,
  "rom.delete": ADMIN_ONLY,

  // Platforms
  "platform.view": ALL_ROLES,
  "platform.create": ADMIN_ONLY,
  "platform.edit": EDITOR_UP,
  "platform.delete": ADMIN_ONLY,

  // Collections — any role can see and curate their own; per-resource
  // ownership checks happen on the backend. The blanket "create" here is
  // the global "is allowed to create some collection" question.
  "collection.view": ALL_ROLES,
  "collection.create": ALL_ROLES,
  "collection.edit": ALL_ROLES,
  "collection.delete": ALL_ROLES,

  // Library
  "library.scan": EDITOR_UP,

  // Users — admin only for now.
  "user.view": ADMIN_ONLY,
  "user.create": ADMIN_ONLY,
  "user.edit": ADMIN_ONLY,
  "user.delete": ADMIN_ONLY,

  // Generic "admin can do this" hatch.
  "app.admin": ADMIN_ONLY,
};

export function actionsForRole(role: Role): ActionKey[] {
  const out: ActionKey[] = [];
  for (const [action, roles] of Object.entries(ACTION_ROLES) as [
    ActionKey,
    Role[],
  ][]) {
    if (roles.includes(role)) out.push(action);
  }
  return out;
}
