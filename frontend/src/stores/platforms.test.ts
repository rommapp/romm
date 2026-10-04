import { describe, expect, it } from "vitest";
import storePlatforms, { type Platform } from "@/stores/platforms";
import { makePlatform } from "@/utils/platform.fixtures";

function platform(id: number, displayName: string, romCount: number): Platform {
  return makePlatform({
    id,
    name: displayName,
    slug: displayName.toLowerCase().replaceAll(" ", "-"),
    rom_count: romCount,
  });
}

describe("platform store lists", () => {
  it("keeps empty platforms reachable from the Platforms index", () => {
    const store = storePlatforms();
    const empty = platform(1, "Game Boy", 0);
    const filled = platform(2, "Nintendo 64", 12);

    store.set([filled, empty]);

    expect(store.allPlatforms).toEqual([filled, empty]);
    expect(store.filledPlatforms).toEqual([filled]);
  });
});
