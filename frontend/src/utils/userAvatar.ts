import { defaultAvatarPath } from "@/utils";

/**
 * Build the URL for a user's avatar.
 *
 * Avatars are dynamic, user-uploaded assets served by the backend user
 * endpoint at `/api/users/<id>/avatar`. This is distinct from the bundled
 * frontend resources under `/assets/romm/...` (`FRONTEND_RESOURCES_PATH`);
 * using that prefix for a user asset yields a broken image.
 *
 * `avatarPath` is used only to tell whether the user has uploaded an avatar;
 * when empty, falls back to the bundled default. The `?ts=` query is
 * cache-busting keyed on the user's `updated_at` so a freshly uploaded avatar
 * isn't served stale from the browser cache.
 */
export function userAvatarUrl({
  userId,
  avatarPath,
  updatedAt,
}: {
  userId: number | null | undefined;
  avatarPath: string | null | undefined;
  updatedAt: string | null | undefined;
}): string {
  if (!avatarPath || userId == null) return defaultAvatarPath;
  return `/api/users/${userId}/avatar?ts=${updatedAt}`;
}
