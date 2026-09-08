import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it } from "vitest";
import storePlatforms, { type Platform } from "@/stores/platforms";

function platform(id: number, displayName: string, romCount: number): Platform {
  return {
    id,
    display_name: displayName,
    name: displayName,
    slug: displayName.toLowerCase().replaceAll(" ", "-"),
    fs_slug: displayName.toLowerCase().replaceAll(" ", "-"),
    rom_count: romCount,
  } as Platform;
}

describe("platform store lists", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
  });

  it("keeps empty platforms reachable from the Platforms index", () => {
    const store = storePlatforms();
    const empty = platform(1, "Game Boy", 0);
    const filled = platform(2, "Nintendo 64", 12);

    store.set([filled, empty]);

    expect(store.allPlatforms).toEqual([filled, empty]);
    expect(store.filledPlatforms).toEqual([filled]);
  });
});
