import { mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Platform } from "@/stores/platforms";
import storePlatforms from "@/stores/platforms";
import PlatformsStatsSection from "./PlatformsStatsSection.vue";

// vue-i18n's `t` is stubbed to echo the key so the component mounts without
// the full i18n plugin.
vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

// The heartbeat store pulls in config + i18n; stub it down to the single
// method this component calls.
vi.mock("@/stores/heartbeat", () => ({
  default: () => ({ getMetadataOptionsByPriority: () => [] }),
}));

function platform(overrides: Partial<Platform> = {}): Platform {
  return {
    id: 1,
    slug: "snes",
    fs_slug: "snes",
    rom_count: 1,
    name: "Super Nintendo",
    igdb_slug: null,
    moby_slug: null,
    hltb_slug: null,
    libretro_slug: null,
    custom_name: "",
    description: null,
    created_at: "",
    updated_at: "",
    fs_size_bytes: 0,
    is_unidentified: false,
    is_identified: true,
    missing_from_fs: false,
    display_name: "Super Nintendo",
    firmware_count: 0,
    ...overrides,
  } as Platform;
}

function mountSection(platforms: Platform[]) {
  storePlatforms().set(platforms);
  return mount(PlatformsStatsSection, {
    props: { totalFilesize: 0, metadataCoverage: {}, regionBreakdown: {} },
    global: {
      stubs: {
        RIcon: true,
        RPlatformIcon: true,
        RProgressLinear: true,
        RSliderBtnGroup: true,
        RTextField: true,
      },
    },
  });
}

function renderedNames(wrapper: ReturnType<typeof mountSection>): string[] {
  return wrapper.findAll(".r-v2-plat-stats__name").map((n) => n.text());
}

describe("PlatformsStatsSection", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
  });

  it("lists only platforms that contain games, hiding empty leftovers", () => {
    const wrapper = mountSection([
      platform({ id: 1, slug: "snes", name: "Super Nintendo", rom_count: 5 }),
      // Ghost platform: emptied long ago, still in the DB with 0 games.
      platform({
        id: 2,
        slug: "xbox360-hacks",
        name: "Xbox360 Hacks",
        display_name: "Xbox360 Hacks",
        rom_count: 0,
      }),
      platform({
        id: 3,
        slug: "genesis",
        name: "Genesis",
        display_name: "Genesis",
        rom_count: 3,
      }),
    ]);

    const names = renderedNames(wrapper);
    expect(names).toEqual(["Genesis", "Super Nintendo"]);
    expect(names).not.toContain("Xbox360 Hacks");
    expect(wrapper.findAll(".r-v2-plat-stats__row")).toHaveLength(2);
  });

  it("renders no rows when every platform is empty", () => {
    const wrapper = mountSection([
      platform({ id: 1, rom_count: 0 }),
      platform({
        id: 2,
        slug: "genesis",
        name: "Genesis",
        display_name: "Genesis",
        rom_count: 0,
      }),
    ]);

    expect(wrapper.findAll(".r-v2-plat-stats__row")).toHaveLength(0);
    expect(wrapper.find(".r-v2-plat-stats__empty").exists()).toBe(true);
  });
});
