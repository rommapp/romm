import { DOMWrapper, flushPromises, mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import { nextTick } from "vue";
import type { Platform } from "@/stores/platforms";
import { makePlatform } from "@/utils/platform.fixtures";
import PlatformSelect from "./PlatformSelect.vue";
import {
  formatPlatformRomCount,
  promotePlatformsWithGamesFirst,
} from "./platformSelect";

vi.mock("vue-i18n");

type Row = Pick<Platform, "rom_count" | "display_name">;

describe("PlatformSelect promoteFilled + search", () => {
  const CATALOG: Platform[] = [
    makePlatform({
      id: 101,
      slug: "3do",
      name: "3DO Interactive Multiplayer",
      rom_count: 0,
    }),
    makePlatform({
      id: 102,
      slug: "ags",
      name: "Adventure Game Studio",
      rom_count: 0,
    }),
    makePlatform({
      id: 4,
      slug: "gba",
      name: "Game Boy Advance",
      rom_count: 42,
    }),
    makePlatform({
      id: 7,
      slug: "snes",
      name: "Super Nintendo",
      rom_count: 256,
    }),
  ];

  function menuRows(): string[] {
    return Array.from(document.querySelectorAll(".r-select__list > li")).map(
      (li) =>
        li.classList.contains("r-select__divider")
          ? "---"
          : (li.querySelector(".r-select__item-title")?.textContent?.trim() ??
            ""),
    );
  }

  function romBadgeFor(displayName: string): string | undefined {
    const row = Array.from(
      document.querySelectorAll(".r-select__list > li:not(.r-select__divider)"),
    ).find(
      (li) =>
        li.querySelector(".r-select__item-title")?.textContent?.trim() ===
        displayName,
    );
    return row?.querySelector(".r-v2-platsel__rom-badge")?.textContent?.trim();
  }

  function panelSearchInput(): DOMWrapper<HTMLInputElement> {
    const el = document.querySelector(".r-select__search input");
    expect(el).not.toBeNull();
    return new DOMWrapper(el as HTMLInputElement);
  }

  async function openPromoteFilledMenu(items: Platform[] = CATALOG) {
    const wrapper = mount(PlatformSelect, {
      props: {
        items,
        promoteFilled: true,
        searchable: true,
        label: "Platforms",
      },
      attachTo: document.body,
    });
    await wrapper.get(".r-select__field").trigger("click");
    await nextTick();
    return wrapper;
  }

  it("partitions filled vs empty when search is empty", async () => {
    await openPromoteFilledMenu();
    const { promoted, remaining } = promotePlatformsWithGamesFirst(CATALOG);

    expect(menuRows()).toEqual([
      ...promoted.map((p) => p.display_name),
      "---",
      ...remaining.map((p) => p.display_name),
    ]);
  });

  it("does not partition while filtering; shows every matching row in item order", async () => {
    await openPromoteFilledMenu();
    await panelSearchInput().setValue("game");
    await flushPromises();
    await nextTick();

    const rows = menuRows();
    expect(rows).not.toContain("---");
    expect(rows).toEqual(["Adventure Game Studio", "Game Boy Advance"]);
    expect(document.querySelectorAll(".r-v2-platsel__rom-badge")).toHaveLength(
      0,
    );
  });

  it("shows neutral rom badges only for promoted rows when partitioned", async () => {
    await openPromoteFilledMenu();
    const badges = Array.from(
      document.querySelectorAll(".r-v2-platsel__rom-badge"),
    );
    expect(badges.length).toBeGreaterThan(0);
    for (const badge of badges) {
      expect(badge.classList.contains("r-tag--neutral")).toBe(true);
    }
    const { remaining } = promotePlatformsWithGamesFirst(CATALOG);
    for (const platform of remaining) {
      expect(romBadgeFor(platform.display_name)).toBeUndefined();
    }
  });

  it("restores partition after search is cleared", async () => {
    await openPromoteFilledMenu();
    await panelSearchInput().setValue("game");
    await flushPromises();
    await nextTick();
    expect(menuRows()).not.toContain("---");

    await panelSearchInput().setValue("");
    await flushPromises();
    await nextTick();

    const { promoted, remaining } = promotePlatformsWithGamesFirst(CATALOG);
    expect(menuRows()).toEqual([
      ...promoted.map((p) => p.display_name),
      "---",
      ...remaining.map((p) => p.display_name),
    ]);
  });
});

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
