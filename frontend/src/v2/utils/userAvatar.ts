import { defaultAvatarPath } from "@/utils";

/**
 * Build the URL for a user's avatar.
 *
 * Avatars are dynamic, user-uploaded assets served by the backend raw-asset
 * endpoint at `/api/raw/assets/<path>` (see backend `models/assets.py` —
 * `download_path`). This is distinct from the bundled frontend resources under
 * `/assets/romm/...` (`FRONTEND_RESOURCES_PATH`); using that prefix for a
 * user asset yields a broken image.
 *
 * The `?ts=` query is cache-busting keyed on the user's `updated_at` so a
 * freshly uploaded avatar isn't served stale from the browser cache. When the
 * user has no uploaded avatar, falls back to the bundled default.
 */
export function userAvatarUrl(
  avatarPath: string | null | undefined,
  updatedAt: string | null | undefined,
): string {
  if (!avatarPath) return defaultAvatarPath;
  return `/api/raw/assets/${avatarPath}?ts=${updatedAt}`;
}
