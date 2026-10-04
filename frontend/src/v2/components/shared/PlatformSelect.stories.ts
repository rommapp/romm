import type { Meta, StoryObj } from "@storybook/vue3-vite";
import { expect, userEvent, within, waitFor } from "storybook/test";
import { ref } from "vue";
import type { Platform } from "@/stores/platforms";
import { platformFixture } from "@/utils/platform.fixtures";
import PlatformSelect from "./PlatformSelect.vue";
import {
  formatPlatformRomCount,
  PLATFORM_ROM_COUNT_CAP,
  promotePlatformsWithGamesFirst,
} from "./platformSelect";

/** Catalog-scale rom counts; PSX is NTSC-U + NTSC-J (~1,278 + ~2,278). */
const PSX_CATALOG_ROM_COUNT = 1278 + 2278;

const MIXED_PLATFORM_CATALOG: Platform[] = [
  platformFixture({
    id: 101,
    slug: "3do",
    name: "3DO Interactive Multiplayer",
    rom_count: 0,
  }),
  platformFixture({
    id: 102,
    slug: "ags",
    name: "Adventure Game Studio",
    rom_count: 0,
  }),
  platformFixture({
    id: 103,
    slug: "amiga",
    name: "Amiga",
    rom_count: 0,
  }),
  platformFixture({
    id: 4,
    slug: "gba",
    name: "Game Boy Advance",
    rom_count: 1537,
  }),
  platformFixture({
    id: 5,
    slug: "n64",
    name: "Nintendo 64",
    rom_count: 389,
  }),
  platformFixture({
    id: 6,
    slug: "psx",
    name: "PlayStation",
    rom_count: PSX_CATALOG_ROM_COUNT,
  }),
  platformFixture({
    id: 7,
    slug: "nes",
    name: "Nintendo Entertainment System",
    rom_count: 722,
  }),
  platformFixture({
    id: 8,
    slug: "zx80",
    name: "ZX80",
    rom_count: 0,
  }),
];

/** One over-cap library plus a normal count for badge formatting. */
const ROM_COUNT_CAP_FIXTURE: Platform[] = [
  platformFixture({
    id: 1,
    slug: "psx",
    name: "PlayStation",
    rom_count: PLATFORM_ROM_COUNT_CAP + 2345,
  }),
  platformFixture({
    id: 2,
    slug: "gba",
    name: "Game Boy Advance",
    rom_count: 99,
  }),
];

function romBadgeText(displayName: string): string | undefined {
  const row = Array.from(
    document.querySelectorAll(".r-select__list > li:not(.r-select__divider)"),
  ).find(
    (li) =>
      li.querySelector(".r-select__item-title")?.textContent?.trim() ===
      displayName,
  );
  return row?.querySelector(".r-v2-platsel__rom-badge")?.textContent?.trim();
}

function menuRowTitles(): string[] {
  return Array.from(document.querySelectorAll(".r-select__list > li")).map(
    (li) =>
      li.classList.contains("r-select__divider")
        ? "---"
        : (li.querySelector(".r-select__item-title")?.textContent?.trim() ??
          ""),
  );
}

function promoteFilledRender() {
  return () => ({
    components: { PlatformSelect },
    setup() {
      const value = ref<number | null>(null);
      const items = ref<Platform[]>([...MIXED_PLATFORM_CATALOG]);
      return { value, items };
    },
    template: `<PlatformSelect v-model="value" :items="items" label="Platforms" :promote-filled="true" />`,
  });
}

async function openMenu(canvasElement: HTMLElement) {
  await userEvent.click(
    within(canvasElement).getByRole("button", { name: "Platforms" }),
  );
  await waitFor(() => {
    expect(document.querySelector(".r-select__panel")).not.toBeNull();
  });
}

// Generic components can't fill Storybook's `component` slot, so it's cast;
// the instantiation types the stories' args.
const meta: Meta<typeof PlatformSelect<number | null>> = {
  title: "Shared/PlatformSelect",
  component: PlatformSelect as never,
  parameters: {
    layout: "padded",
  },
  decorators: [
    () => ({
      template: `<div style="width:min(360px,100%);padding-top:8px"><story /></div>`,
    }),
  ],
};

export default meta;
type Story = StoryObj<typeof meta>;

export const CallerOrder: Story = {
  name: "Caller order (promotion off)",
  render: () => ({
    components: { PlatformSelect },
    setup() {
      const value = ref<number | null>(null);
      const items = ref<Platform[]>([...MIXED_PLATFORM_CATALOG]);
      return { value, items };
    },
    template: `<PlatformSelect v-model="value" :items="items" :promote-filled="false" label="Platforms" />`,
  }),
};

export const PromotedOnPage: Story = {
  name: "Promotion on — on page",
  render: promoteFilledRender(),
};

export const PromotedOpenMenu: Story = {
  name: "Promotion on — open menu, do not type",
  render: promoteFilledRender(),
  play: async ({ canvasElement, step }) => {
    await step("open menu (do not type in search)", async () => {
      await openMenu(canvasElement);
    });

    await step("partitioned list", async () => {
      const { promoted, remaining } = promotePlatformsWithGamesFirst(
        MIXED_PLATFORM_CATALOG,
      );
      expect(menuRowTitles()).toEqual([
        ...promoted.map((p) => p.display_name),
        "---",
        ...remaining.map((p) => p.display_name),
      ]);
    });

    await step("rom count badges when partitioned", async () => {
      const gbaRow = document.querySelector(
        ".r-select__list > li:not(.r-select__divider)",
      );
      expect(
        gbaRow?.querySelector(".r-v2-platsel__rom-badge")?.textContent,
      ).toBe("1537");
    });
  },
};

export const PromotedRomCountCap: Story = {
  name: "Promotion on — rom count 9999+ cap",
  render: () => ({
    components: { PlatformSelect },
    setup() {
      const value = ref<number | null>(null);
      const items = ref<Platform[]>([...ROM_COUNT_CAP_FIXTURE]);
      return { value, items };
    },
    template: `<PlatformSelect v-model="value" :items="items" label="Platforms" :promote-filled="true" />`,
  }),
  play: async ({ canvasElement, step }) => {
    await step("open menu", async () => {
      await openMenu(canvasElement);
    });

    await step("caps badge at 9999+", async () => {
      await waitFor(() => {
        expect(romBadgeText("PlayStation")).toBe(
          formatPlatformRomCount(PLATFORM_ROM_COUNT_CAP + 2345),
        );
        expect(romBadgeText("Game Boy Advance")).toBe("99");
      });
    });
  },
};

export const PromotedTypingInSearch: Story = {
  name: "Promotion on — typing in panel search",
  render: promoteFilledRender(),
  play: async ({ canvasElement, step }) => {
    const searchCharacter = "g";
    await step("open menu", async () => {
      await openMenu(canvasElement);
    });

    await step("type in panel search", async () => {
      const search = document.querySelector(
        ".r-select__search input",
      ) as HTMLInputElement;
      expect(search).not.toBeNull();
      await userEvent.click(search);
      await userEvent.type(search, searchCharacter);
    });

    await step("no partition; caller item order", async () => {
      await waitFor(() => {
        const rows = menuRowTitles();
        expect(rows).not.toContain("---");
        expect(rows).toEqual([
          "Adventure Game Studio",
          "Amiga",
          "Game Boy Advance",
        ]);
        expect(
          document.querySelectorAll(".r-v2-platsel__rom-badge"),
        ).toHaveLength(0);
      });
    });
  },
};

export const PromotedSearchDisabled: Story = {
  name: "Promotion on — search field disabled",
  render: () => ({
    components: { PlatformSelect },
    setup() {
      const value = ref<number | null>(null);
      const items = ref<Platform[]>([...MIXED_PLATFORM_CATALOG]);
      return { value, items };
    },
    template: `<PlatformSelect v-model="value" :items="items" label="Platforms" :promote-filled="true" :searchable="false" />`,
  }),
  play: async ({ canvasElement, step }) => {
    await step("open menu", async () => {
      await openMenu(canvasElement);
      expect(document.querySelector(".r-select__search")).toBeNull();
    });

    await step("still partitioned", async () => {
      const { promoted, remaining } = promotePlatformsWithGamesFirst(
        MIXED_PLATFORM_CATALOG,
      );
      expect(menuRowTitles()).toEqual([
        ...promoted.map((p) => p.display_name),
        "---",
        ...remaining.map((p) => p.display_name),
      ]);
    });
  },
};

export const PromotedAllLibrariesEmpty: Story = {
  name: "Promotion on — every library empty",
  render: () => ({
    components: { PlatformSelect },
    setup() {
      const value = ref<number | null>(null);
      const items = ref<Platform[]>(
        MIXED_PLATFORM_CATALOG.map((p) => ({ ...p, rom_count: 0 })),
      );
      return { value, items };
    },
    template: `<PlatformSelect v-model="value" :items="items" label="Platforms" :promote-filled="true" />`,
  }),
};

export const ScanPagePicker: Story = {
  name: "Scan page picker, promotion on",
  render: () => ({
    components: { PlatformSelect },
    setup() {
      const value = ref<string[]>([]);
      const items = ref<Platform[]>([...MIXED_PLATFORM_CATALOG]);
      return { value, items };
    },
    // The same props Scan.vue passes.
    template: `<PlatformSelect v-model="value" :items="items" item-key="fs_slug" label="Platforms" multiple clearable hide-details chips show-meta mark-unscanned show-all-option promote-filled />`,
  }),
  play: async ({ canvasElement, step }) => {
    await step("open menu", async () => {
      await openMenu(canvasElement);
    });

    await step(
      "platforms with games come first, below the All row",
      async () => {
        const { promoted, remaining } = promotePlatformsWithGamesFirst(
          MIXED_PLATFORM_CATALOG,
        );
        expect(menuRowTitles()).toEqual([
          "All",
          "---",
          ...promoted.map((p) => p.display_name),
          "---",
          ...remaining.map((p) => p.display_name),
        ]);
      },
    );
  },
};
