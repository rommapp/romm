import type { Meta, StoryObj } from "@storybook/vue3-vite";
import { expect, userEvent, within, waitFor } from "storybook/test";
import { ref } from "vue";
import type { Platform } from "@/stores/platforms";
import PlatformSelect from "./PlatformSelect.vue";
import { promotePlatformsWithGamesFirst } from "./platformsWithGamesFirst";

function makePlatform(overrides: Partial<Platform> = {}): Platform {
  const slug = overrides.slug ?? "platform";
  return {
    id: -1,
    slug,
    fs_slug: overrides.fs_slug ?? slug,
    rom_count: 0,
    name: overrides.name ?? "Platform",
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
    display_name: overrides.display_name ?? "Platform",
    firmware_count: 0,
    ...overrides,
  };
}

/** Catalog-scale rom counts; PSX is NTSC-U + NTSC-J (~1,278 + ~2,278). */
const PSX_CATALOG_ROM_COUNT = 1278 + 2278;

const MIXED_PLATFORM_CATALOG: Platform[] = [
  makePlatform({
    id: 101,
    slug: "3do",
    name: "3DO Interactive Multiplayer",
    display_name: "3DO Interactive Multiplayer",
    rom_count: 0,
  }),
  makePlatform({
    id: 102,
    slug: "ags",
    name: "Adventure Game Studio",
    display_name: "Adventure Game Studio",
    rom_count: 0,
  }),
  makePlatform({
    id: 103,
    slug: "amiga",
    name: "Amiga",
    display_name: "Amiga",
    rom_count: 0,
  }),
  makePlatform({
    id: 4,
    slug: "gba",
    name: "Game Boy Advance",
    display_name: "Game Boy Advance",
    rom_count: 1537,
  }),
  makePlatform({
    id: 5,
    slug: "n64",
    name: "Nintendo 64",
    display_name: "Nintendo 64",
    rom_count: 389,
  }),
  makePlatform({
    id: 6,
    slug: "psx",
    name: "PlayStation",
    display_name: "PlayStation",
    rom_count: PSX_CATALOG_ROM_COUNT,
  }),
  makePlatform({
    id: 7,
    slug: "snes",
    name: "Super Nintendo",
    display_name: "Super Nintendo",
    rom_count: 722,
  }),
  makePlatform({
    id: 8,
    slug: "zx80",
    name: "ZX80",
    display_name: "ZX80",
    rom_count: 0,
  }),
];

const meta: Meta<typeof PlatformSelect> = {
  title: "Shared/PlatformSelect",
  component: PlatformSelect,
  parameters: {
    // Global preview uses centered layout; menus need headroom below the field.
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

const LABEL = "Platforms";

// promoteFilled is off: menu order must match `items` as passed (no reorder).
export const PlatformSelectDefault: Story = {
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

// Opt-in preview: filled platforms first (name sort), divider, then empties.
export const PlatformSelectorPromoteFilled: Story = {
  render: () => ({
    components: { PlatformSelect },
    setup() {
      const value = ref<number | null>(null);
      const items = ref<Platform[]>([...MIXED_PLATFORM_CATALOG]);
      return { value, items };
    },
    template: `<PlatformSelect v-model="value" :items="items" label="Platforms" :promote-filled="true" />`,
  }),
  play: async ({ canvasElement, step }) => {
    await step("open menu", async () => {
      await userEvent.click(
        within(canvasElement).getByRole("button", { name: LABEL }),
      );
      await waitFor(() => {
        expect(document.querySelector(".r-select__panel")).not.toBeNull();
      });
    });

    await step(
      "filled block, divider, then empty block (promote on)",
      async () => {
        const { promoted, remaining } = promotePlatformsWithGamesFirst(
          MIXED_PLATFORM_CATALOG,
        );
        const rows = Array.from(
          document.querySelectorAll(".r-select__list > li"),
        ).map((li) =>
          li.classList.contains("r-select__divider")
            ? "---"
            : (li.querySelector(".r-select__item-title")?.textContent?.trim() ??
              ""),
        );
        expect(rows).toEqual([
          ...promoted.map((p) => p.display_name),
          "---",
          ...remaining.map((p) => p.display_name),
        ]);
        const gbaRow = document.querySelector(
          ".r-select__list > li:not(.r-select__divider)",
        );
        expect(
          gbaRow?.querySelector(".r-v2-platsel__rom-badge")?.textContent,
        ).toBe("1537");
        const psxRow = Array.from(
          document.querySelectorAll(
            ".r-select__list > li:not(.r-select__divider)",
          ),
        ).find(
          (li) =>
            li.querySelector(".r-select__item-title")?.textContent?.trim() ===
            "PlayStation",
        );
        expect(
          psxRow?.querySelector(".r-v2-platsel__rom-badge")?.textContent,
        ).toBe(String(PSX_CATALOG_ROM_COUNT));
      },
    );
  },
};

// promoteFilled on but every row empty: no divider, name sort only.
export const PlatformSelectorPromoteButNotFilled: Story = {
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
