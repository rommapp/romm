import { describe, expect, it } from "vitest";
import type { Platform } from "@/stores/platforms";
import {
  formatPlatformRomCount,
  promotePlatformsWithGamesFirst,
} from "./platformSelect";

type Row = Pick<Platform, "rom_count" | "display_name">;

describe("promotePlatformsWithGamesFirst", () => {
  it("sorts by display_name and puts rom_count > 0 in promoted", () => {
    const items: Row[] = [
      { display_name: "Amiga", rom_count: 0 },
      { display_name: "ZX Spectrum", rom_count: 3 },
      { display_name: "SNES", rom_count: 12 },
    ];

    const { promoted, remaining } = promotePlatformsWithGamesFirst(items);

    expect(promoted.map((p) => p.display_name)).toEqual([
      "SNES",
      "ZX Spectrum",
    ]);
    expect(remaining.map((p) => p.display_name)).toEqual(["Amiga"]);
  });

  it("returns every row across promoted and remaining", () => {
    const items: Row[] = [
      { display_name: "Amiga", rom_count: 0 },
      { display_name: "ZX Spectrum", rom_count: 3 },
      { display_name: "SNES", rom_count: 12 },
    ];

    const { promoted, remaining } = promotePlatformsWithGamesFirst(items);

    expect(promoted.length + remaining.length).toBe(items.length);
    expect(
      [...promoted, ...remaining].map((p) => p.display_name).sort(),
    ).toEqual(items.map((p) => p.display_name).sort());
  });

  it("treats rom_count > 0 as promoted regardless of name order in the input", () => {
    const items: Row[] = [
      { display_name: "ZX Spectrum", rom_count: 1 },
      { display_name: "Amiga", rom_count: 0 },
    ];

    const { promoted, remaining } = promotePlatformsWithGamesFirst(items);

    expect(promoted.map((p) => p.display_name)).toEqual(["ZX Spectrum"]);
    expect(remaining.map((p) => p.display_name)).toEqual(["Amiga"]);
  });

  it("returns empty remaining when every platform has games", () => {
    const items: Row[] = [
      { display_name: "SNES", rom_count: 2 },
      { display_name: "NES", rom_count: 1 },
    ];

    const { promoted, remaining } = promotePlatformsWithGamesFirst(items);

    expect(promoted.map((p) => p.display_name)).toEqual(["NES", "SNES"]);
    expect(remaining).toEqual([]);
  });

  it("returns empty promoted when no platform has games", () => {
    const items: Row[] = [
      { display_name: "3DO", rom_count: 0 },
      { display_name: "Amiga", rom_count: 0 },
    ];

    const { promoted, remaining } = promotePlatformsWithGamesFirst(items);

    expect(promoted).toEqual([]);
    expect(remaining.map((p) => p.display_name)).toEqual(["3DO", "Amiga"]);
  });

  it("returns empty promoted and remaining for an empty list", () => {
    expect(promotePlatformsWithGamesFirst([])).toEqual({
      promoted: [],
      remaining: [],
    });
  });
});

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
