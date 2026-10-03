import { describe, expect, it } from "vitest";
import storeRoms, {
  DETAILED_ROM_CACHE_SIZE,
  type DetailedRom,
} from "@/stores/roms";
import { makeDetailedRom, makeRom } from "@/utils/rom.fixtures";

function detailed(id: number, extra: Partial<DetailedRom> = {}) {
  return makeDetailedRom({ id, name: `Game ${id}`, ...extra });
}

describe("detailed rom cache", () => {
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
    for (let id = 1; id <= DETAILED_ROM_CACHE_SIZE; id++) {
      roms.cacheDetailedRom(detailed(id));
    }

    // Re-caching game 1 makes game 2 the oldest.
    roms.cacheDetailedRom(detailed(1));
    roms.cacheDetailedRom(detailed(99));

    expect(roms.getDetailedRom(1)).not.toBeNull();
    expect(roms.getDetailedRom(2)).toBeNull();
    expect(roms.getDetailedRom(99)).not.toBeNull();
    expect(roms.detailedRoms.size).toBe(DETAILED_ROM_CACHE_SIZE);
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

    roms.update(makeRom({ id: 5, name: "Renamed" }));

    expect(roms.getDetailedRom(5)).toMatchObject({
      name: "Renamed",
      summary: "detailed",
    });
  });

  it("caches nothing for a write to a game it doesn't hold", () => {
    const roms = storeRoms();

    roms.mergeIntoDetailedRom(makeRom({ id: 6, name: "Elsewhere" }));

    expect(roms.getDetailedRom(6)).toBeNull();
  });

  it("forgets deleted games", () => {
    const roms = storeRoms();
    roms.cacheDetailedRom(detailed(7));
    roms.cacheDetailedRom(detailed(8));

    roms.forgetDetailedRoms([7]);

    expect(roms.getDetailedRom(7)).toBeNull();
    expect(roms.getDetailedRom(8)).not.toBeNull();
  });

  it("empties the cache on reset, so logout keeps no record", () => {
    const roms = storeRoms();
    roms.setCurrentRom(detailed(9));

    roms.reset();

    expect(roms.getDetailedRom(9)).toBeNull();
  });
});
