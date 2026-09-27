import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it } from "vitest";
import storeRoms, { type DetailedRom, type SimpleRom } from "@/stores/roms";

function detailed(id: number, overrides: Partial<DetailedRom> = {}) {
  return { id, name: `Game ${id}`, ...overrides } as DetailedRom;
}

describe("detailed rom cache", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
  });

  it("keeps each game under its own id", () => {
    const roms = storeRoms();

    roms.cacheDetailedRom(detailed(1));
    roms.cacheDetailedRom(detailed(2));

    expect(roms.getDetailedRom(1)?.name).toBe("Game 1");
    expect(roms.getDetailedRom(2)?.name).toBe("Game 2");
    expect(roms.getDetailedRom(3)).toBeNull();
  });

  it("drops the least recently cached game past its bound", () => {
    const roms = storeRoms();
    for (let id = 1; id <= 10; id++) roms.cacheDetailedRom(detailed(id));

    // Re-caching game 1 makes game 2 the oldest.
    roms.cacheDetailedRom(detailed(1));
    roms.cacheDetailedRom(detailed(11));

    expect(roms.getDetailedRom(1)).not.toBeNull();
    expect(roms.getDetailedRom(2)).toBeNull();
    expect(roms.getDetailedRom(11)).not.toBeNull();
    expect(roms.detailedRoms.size).toBe(10);
  });

  it("caches the rom the route guard sets as current", () => {
    const roms = storeRoms();

    roms.setCurrentRom(detailed(4));

    expect(roms.currentRom?.id).toBe(4);
    expect(roms.getDetailedRom(4)?.id).toBe(4);
  });

  it("merges a SimpleRom write over the detailed record", () => {
    const roms = storeRoms();
    roms.cacheDetailedRom(detailed(5, { summary: "detailed" }));

    roms.update({ id: 5, name: "Renamed" } as SimpleRom);

    expect(roms.getDetailedRom(5)).toMatchObject({
      name: "Renamed",
      summary: "detailed",
    });
  });

  it("caches nothing for a write to a game it doesn't hold", () => {
    const roms = storeRoms();

    roms.mergeIntoDetailedRom({ id: 6, name: "Elsewhere" } as SimpleRom);

    expect(roms.getDetailedRom(6)).toBeNull();
  });
});
