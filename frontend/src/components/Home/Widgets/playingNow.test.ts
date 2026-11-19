import { describe, expect, it } from "vitest";
import type { ActivityEntry } from "@/services/api/activity";
import { pickPlayingNow } from "./playingNow";

function entry(
  overrides: Partial<ActivityEntry> & {
    user_id: number;
    rom_id: number;
    started_at: string;
  },
): ActivityEntry {
  return {
    username: `user${overrides.user_id}`,
    avatar_path: "",
    rom_name: `rom${overrides.rom_id}`,
    rom_cover_path: "",
    screenshot_path: "",
    platform_slug: "snes",
    platform_name: "SNES",
    device_id: `device-${overrides.user_id}`,
    device_type: "web",
    ...overrides,
  };
}

describe("pickPlayingNow", () => {
  it("returns null when nobody is playing", () => {
    expect(pickPlayingNow([])).toBeNull();
  });

  it("picks the game with the most players", () => {
    const pick = pickPlayingNow([
      entry({ user_id: 1, rom_id: 10, started_at: "2026-01-01T10:00:00Z" }),
      entry({ user_id: 2, rom_id: 20, started_at: "2026-01-01T11:00:00Z" }),
      entry({ user_id: 3, rom_id: 20, started_at: "2026-01-01T12:00:00Z" }),
    ]);

    expect(pick?.lead.rom_id).toBe(20);
    expect(pick?.lead.user_id).toBe(2);
    expect(pick?.playerCount).toBe(2);
    expect(pick?.otherGames).toBe(1);
  });

  it("breaks a tie with the longest-running session", () => {
    const pick = pickPlayingNow([
      entry({ user_id: 1, rom_id: 10, started_at: "2026-01-01T12:00:00Z" }),
      entry({ user_id: 2, rom_id: 20, started_at: "2026-01-01T09:00:00Z" }),
    ]);

    expect(pick?.lead.rom_id).toBe(20);
  });

  it("counts a player's twin entries for one game once", () => {
    const pick = pickPlayingNow([
      entry({ user_id: 1, rom_id: 10, started_at: "2026-01-01T10:00:00Z" }),
      entry({
        user_id: 1,
        rom_id: 10,
        device_id: "container-1",
        device_type: "streaming",
        started_at: "2026-01-01T10:00:01Z",
      }),
    ]);

    expect(pick?.playerCount).toBe(1);
    expect(pick?.otherGames).toBe(0);
  });
});
