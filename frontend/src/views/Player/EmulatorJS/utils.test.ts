import { describe, expect, it } from "vitest";
import {
  getPlayerBiosStorageKey,
  getPlayerCoreStorageKey,
  getPlayerPlatformStorageSlug,
} from "./utils";

describe("EmulatorJS player storage keys", () => {
  it("uses the filesystem slug for per-platform preferences when available", () => {
    const platform = {
      platform_slug: "arcade",
      platform_fs_slug: "cps3",
    };

    expect(getPlayerPlatformStorageSlug(platform)).toBe("cps3");
    expect(getPlayerCoreStorageKey(platform)).toBe("player:cps3:core");
    expect(getPlayerBiosStorageKey(platform)).toBe("player:cps3:bios_id");
  });

  it("falls back to the effective platform slug when no filesystem slug exists", () => {
    const platform = {
      platform_slug: "arcade",
      platform_fs_slug: "",
    };

    expect(getPlayerPlatformStorageSlug(platform)).toBe("arcade");
    expect(getPlayerCoreStorageKey(platform)).toBe("player:arcade:core");
    expect(getPlayerBiosStorageKey(platform)).toBe("player:arcade:bios_id");
  });
});
