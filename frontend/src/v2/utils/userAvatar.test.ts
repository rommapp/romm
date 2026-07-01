import { describe, expect, it } from "vitest";
import { defaultAvatarPath } from "@/utils";
import { userAvatarUrl } from "./userAvatar";

describe("userAvatarUrl", () => {
  it("builds an id-based avatar URL for an uploaded avatar", () => {
    expect(
      userAvatarUrl(
        42,
        "users/abc/profile/avatar.png",
        "2026-06-17T10:58:32+00:00",
      ),
    ).toBe("/api/users/42/avatar?ts=2026-06-17T10:58:32+00:00");
  });

  it("uses the /api/users prefix, not the static frontend mount", () => {
    const url = userAvatarUrl(42, "users/abc/profile/avatar.png", "ts");
    expect(url.startsWith("/api/users/")).toBe(true);
    expect(url).not.toContain("/assets/romm/");
  });

  it("falls back to the default avatar when no path or id is set", () => {
    expect(userAvatarUrl(42, "", "2026-06-17")).toBe(defaultAvatarPath);
    expect(userAvatarUrl(null, "users/abc/profile/avatar.png", "ts")).toBe(
      defaultAvatarPath,
    );
    expect(userAvatarUrl(undefined, undefined, undefined)).toBe(
      defaultAvatarPath,
    );
  });
});
