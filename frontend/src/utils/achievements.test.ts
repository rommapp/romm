import { describe, expect, it } from "vitest";
import type { RAGameRomAchievement } from "@/__generated__";
import { earnedAchievementKeys, isAchievementEarned } from "./achievements";

function achievement(ra_id: number, badge_id: string): RAGameRomAchievement {
  return {
    ra_id,
    title: null,
    description: null,
    points: null,
    num_awarded: null,
    num_awarded_hardcore: null,
    badge_id,
    badge_url_lock: null,
    badge_path_lock: null,
    badge_url: null,
    badge_path: null,
    display_order: null,
    type: null,
  };
}

describe("isAchievementEarned", () => {
  const shared = [1, 2, 3].map((id) => achievement(id, "217206"));

  it("counts each earned achievement that shares a badge", () => {
    const keys = earnedAchievementKeys([
      { id: "217206", ra_id: 1, date: "2026-01-01" },
      { id: "217206", ra_id: 3, date: "2026-01-01" },
    ]);

    expect(shared.map((a) => isAchievementEarned(a, keys))).toEqual([
      true,
      false,
      true,
    ]);
  });

  it("falls back to the badge for entries synced without an id", () => {
    const keys = earnedAchievementKeys([{ id: "217206", date: "2026-01-01" }]);

    expect(shared.every((a) => isAchievementEarned(a, keys))).toBe(true);
    expect(isAchievementEarned(achievement(4, "other"), keys)).toBe(false);
  });
});
