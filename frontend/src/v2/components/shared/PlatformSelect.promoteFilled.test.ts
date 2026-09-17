import { DOMWrapper, flushPromises, mount } from "@vue/test-utils";
import { afterEach, describe, expect, it, vi } from "vitest";
import { nextTick } from "vue";
import type { Platform } from "@/stores/platforms";
import PlatformSelect from "./PlatformSelect.vue";
import { promotePlatformsWithGamesFirst } from "./platformsWithGamesFirst";

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

function makePlatform(
  overrides: Pick<Platform, "id" | "display_name" | "slug" | "rom_count"> &
    Partial<Platform>,
): Platform {
  const slug = overrides.slug;
  return {
    id: overrides.id,
    slug,
    fs_slug: slug,
    rom_count: overrides.rom_count,
    name: overrides.display_name,
    display_name: overrides.display_name,
    igdb_slug: null,
    moby_slug: null,
    hltb_slug: null,
    libretro_slug: null,
    created_at: "",
    updated_at: "",
    fs_size_bytes: 0,
    is_unidentified: false,
    is_identified: true,
    missing_from_fs: false,
    firmware_count: 0,
    ...overrides,
  };
}

const CATALOG: Platform[] = [
  makePlatform({
    id: 101,
    slug: "3do",
    display_name: "3DO Interactive Multiplayer",
    rom_count: 0,
  }),
  makePlatform({
    id: 102,
    slug: "ags",
    display_name: "Adventure Game Studio",
    rom_count: 0,
  }),
  makePlatform({
    id: 4,
    slug: "gba",
    display_name: "Game Boy Advance",
    rom_count: 42,
  }),
  makePlatform({
    id: 7,
    slug: "snes",
    display_name: "Super Nintendo",
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

function panelSearchInput(): DOMWrapper<HTMLInputElement> {
  const el = document.querySelector(".r-select__search input");
  expect(el).not.toBeNull();
  return new DOMWrapper(el as HTMLInputElement);
}

async function openPromoteFilledMenu(items: Platform[] = CATALOG) {
  document.body.innerHTML = "";
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

afterEach(() => {
  document.body.innerHTML = "";
});

describe("PlatformSelect promoteFilled + search", () => {
  it("partitions filled vs empty when search is empty", async () => {
    const wrapper = await openPromoteFilledMenu();
    const { promoted, remaining } = promotePlatformsWithGamesFirst(CATALOG);

    expect(menuRows()).toEqual([
      ...promoted.map((p) => p.display_name),
      "---",
      ...remaining.map((p) => p.display_name),
    ]);

    wrapper.unmount();
  });

  it("does not partition while filtering; shows every matching row in item order", async () => {
    const wrapper = await openPromoteFilledMenu();
    await panelSearchInput().setValue("game");
    await flushPromises();
    await nextTick();

    const rows = menuRows();
    expect(rows).not.toContain("---");
    expect(rows).toEqual(["Adventure Game Studio", "Game Boy Advance"]);

    wrapper.unmount();
  });

  it("restores partition after search is cleared", async () => {
    const wrapper = await openPromoteFilledMenu();
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

    wrapper.unmount();
  });
});
