import { describe, expect, it } from "vitest";
import { clearOwnerlessOwnOnly } from "@/utils/permissionGrants";

describe("clearOwnerlessOwnOnly", () => {
  it("clears own_only only on entities without an owner", () => {
    const grants = [
      { entity: "users" as const, action: "write" as const, own_only: true },
      {
        entity: "collections" as const,
        action: "write" as const,
        own_only: true,
      },
      { entity: "roms" as const, action: "read" as const, own_only: false },
    ];

    expect(clearOwnerlessOwnOnly(grants, ["collections"])).toEqual([
      { entity: "users", action: "write", own_only: false },
      { entity: "collections", action: "write", own_only: true },
      { entity: "roms", action: "read", own_only: false },
    ]);
  });
});
