import { describe, expect, it } from "vitest";
import {
  grantEffect,
  normalizeOwnerlessGrants,
  normalizeOwnerlessOverrides,
} from "@/utils/permissionGrants";

describe("grantEffect", () => {
  it("reads owner-less own_only as its coarse scope", () => {
    const ownable = ["collections" as const];
    expect(
      grantEffect(
        { entity: "users", action: "write", own_only: true },
        ownable,
      ),
    ).toBe("full");
    expect(
      grantEffect(
        { entity: "roms", action: "delete", own_only: true },
        ownable,
      ),
    ).toBe("none");
    expect(
      grantEffect(
        { entity: "collections", action: "delete", own_only: true },
        ownable,
      ),
    ).toBe("own");
  });
});

describe("normalizeOwnerlessGrants", () => {
  it("keeps what each owner-less own_only grant already allows", () => {
    expect(
      normalizeOwnerlessGrants(
        [
          { entity: "users", action: "write", own_only: true },
          { entity: "roms", action: "delete", own_only: true },
          { entity: "collections", action: "write", own_only: true },
          { entity: "roms", action: "read", own_only: false },
        ],
        ["collections"],
      ),
    ).toEqual([
      { entity: "users", action: "write", own_only: false },
      { entity: "collections", action: "write", own_only: true },
      { entity: "roms", action: "read", own_only: false },
    ]);
  });
});

describe("normalizeOwnerlessOverrides", () => {
  it("turns an owner-less own_only delete into a revoke", () => {
    expect(
      normalizeOwnerlessOverrides(
        [
          { entity: "users", action: "write", granted: true, own_only: true },
          { entity: "roms", action: "delete", granted: true, own_only: true },
          { entity: "tasks", action: "write", granted: false, own_only: true },
          { entity: "devices", action: "write", granted: true, own_only: true },
        ],
        ["devices"],
      ),
    ).toEqual([
      { entity: "users", action: "write", granted: true, own_only: false },
      { entity: "roms", action: "delete", granted: false, own_only: false },
      { entity: "tasks", action: "write", granted: false, own_only: false },
      { entity: "devices", action: "write", granted: true, own_only: true },
    ]);
  });
});
