import { describe, expect, it } from "vitest";
import { formatPlatformRomCount } from "./formatPlatformRomCount";

describe("formatPlatformRomCount", () => {
  it("stringifies counts at or below the cap", () => {
    expect(formatPlatformRomCount(0)).toBe("0");
    expect(formatPlatformRomCount(42)).toBe("42");
    expect(formatPlatformRomCount(9999)).toBe("9999");
  });

  it("shows 9999+ above the cap", () => {
    expect(formatPlatformRomCount(10_000)).toBe("9999+");
  });
});
