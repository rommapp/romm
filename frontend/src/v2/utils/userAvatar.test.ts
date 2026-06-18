import { describe, expect, it } from "vitest";
import { defaultAvatarPath } from "@/utils";
import { userAvatarUrl } from "./userAvatar";

describe("userAvatarUrl", () => {
  it("builds a raw-asset URL for an uploaded avatar", () => {
    expect(
      userAvatarUrl(
        "users/abc/profile/avatar.png",
        "2026-06-17T10:58:32+00:00",
      ),
    ).toBe(
      "/api/raw/assets/users/abc/profile/avatar.png?ts=2026-06-17T10:58:32+00:00",
    );
  });

  it("uses the /api/raw/assets prefix, not the static frontend mount", () => {
    const url = userAvatarUrl("users/abc/profile/avatar.png", "ts");
    expect(url.startsWith("/api/raw/assets/")).toBe(true);
    expect(url).not.toContain("/assets/romm/");
  });

  it("falls back to the default avatar when no path is set", () => {
    expect(userAvatarUrl("", "2026-06-17")).toBe(defaultAvatarPath);
    expect(userAvatarUrl(null, null)).toBe(defaultAvatarPath);
    expect(userAvatarUrl(undefined, undefined)).toBe(defaultAvatarPath);
  });
});
