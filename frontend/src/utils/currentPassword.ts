import type { UserSchema } from "@/__generated__";

/**
 * Whether the backend asks for the current password before saving a self-edit:
 * a new password or email on an account that has a password.
 */
export function needsCurrentPassword(
  saved: Pick<UserSchema, "email" | "has_password">,
  edit: { password?: string; email?: string | null },
): boolean {
  if (!saved.has_password) return false;
  if (edit.password) return true;
  return (
    edit.email != null &&
    edit.email.toLowerCase() !== (saved.email ?? "").toLowerCase()
  );
}
