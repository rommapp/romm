import type { UserSchema } from "@/__generated__";

function changed(saved: string | null, edit: string | null | undefined) {
  return edit != null && edit.toLowerCase() !== (saved ?? "").toLowerCase();
}

/**
 * Whether the backend asks for the current password before saving a self-edit:
 * a new username, password or email on an account that has a password.
 */
export function needsCurrentPassword(
  saved: Pick<UserSchema, "username" | "email" | "has_password">,
  edit: { username?: string; password?: string; email?: string | null },
): boolean {
  if (!saved.has_password) return false;
  return (
    !!edit.password ||
    (!!edit.username && changed(saved.username, edit.username)) ||
    changed(saved.email, edit.email)
  );
}
