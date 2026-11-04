import type { EarnedAchievement, RAGameRomAchievement } from "@/__generated__";

/** Lookup keys for a user's earned achievements, read by `isAchievementEarned`. */
export function earnedAchievementKeys(
  earned: readonly EarnedAchievement[],
): ReadonlySet<string> {
  // Entries synced before `ra_id` existed carry only the shared badge name.
  return new Set(
    earned.map((e) => (e.ra_id != null ? `ra:${e.ra_id}` : `badge:${e.id}`)),
  );
}

export function isAchievementEarned(
  achievement: RAGameRomAchievement,
  earnedKeys: ReadonlySet<string>,
): boolean {
  if (achievement.ra_id != null && earnedKeys.has(`ra:${achievement.ra_id}`)) {
    return true;
  }
  return Boolean(
    achievement.badge_id && earnedKeys.has(`badge:${achievement.badge_id}`),
  );
}
