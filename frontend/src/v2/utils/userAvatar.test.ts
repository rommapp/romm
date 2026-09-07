import { describe, expect, it } from "vitest";
import { defaultAvatarPath } from "@/utils";
import { userAvatarUrl } from "./userAvatar";

describe("userAvatarUrl", () => {
  it("builds an id-based avatar URL for an uploaded avatar", () => {
    expect(
      userAvatarUrl({
        userId: 42,
        avatarPath: "users/abc/profile/avatar.png",
        updatedAt: "2026-06-17T10:58:32+00:00",
      }),
    ).toBe("/api/users/42/avatar?ts=2026-06-17T10:58:32+00:00");
  });

  it("uses the /api/users prefix, not the static frontend mount", () => {
    const url = userAvatarUrl({
      userId: 42,
      avatarPath: "users/abc/profile/avatar.png",
      updatedAt: "ts",
    });
    expect(url.startsWith("/api/users/")).toBe(true);
    expect(url).not.toContain("/assets/romm/");
  });

  it("falls back to the default avatar when no path or id is set", () => {
    expect(
      userAvatarUrl({ userId: 42, avatarPath: "", updatedAt: "2026-06-17" }),
    ).toBe(defaultAvatarPath);
    expect(
      userAvatarUrl({
        userId: null,
        avatarPath: "users/abc/profile/avatar.png",
        updatedAt: "ts",
      }),
    ).toBe(defaultAvatarPath);
    expect(
      userAvatarUrl({
        userId: undefined,
        avatarPath: undefined,
        updatedAt: undefined,
      }),
    ).toBe(defaultAvatarPath);
  });
});
