import type { Platform } from "@/stores/platforms";

export function platformFixture(overrides: Partial<Platform> = {}): Platform {
  const slug = overrides.slug ?? "platform";
  const name = overrides.name ?? "Platform";
  return {
    id: 1,
    slug,
    fs_slug: slug,
    rom_count: 0,
    name,
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
    display_name: name,
    firmware_count: 0,
    abbreviation: "",
    alternative_names: [],
    ...overrides,
  };
}
