// Metadata-provider registry — single source of truth for the small
// provider chips that appear next to a ROM (gallery list rows, scan
// rows, future surfaces). One entry per provider gives label + logo
// path + (optional) brand-colour background; consumers iterate and
// filter to the providers whose id field is populated on the ROM.
import type { SimpleRom } from "@/stores/roms";

/** Subset of `SimpleRom` fields that hold a matched provider id. Keying
 * the list against this type means a typo or a removed field is a
 * compile error, not a silent miss. */
export type ProviderIdKey =
  | "hasheous_id"
  | "igdb_id"
  | "ss_id"
  | "moby_id"
  | "launchbox_id"
  | "ra_id"
  | "flashpoint_id"
  | "hltb_id"
  | "gamelist_id"
  | "libretro_id";

export interface MetadataProvider {
  /** Field on `SimpleRom` that holds this provider's match id. */
  key: ProviderIdKey;
  /** Short brand name (e.g. "IGDB") — used as the gallery filter label. */
  name: string;
  /** Tooltip text — also serves as the chip's `alt`. */
  title: string;
  /** File under `/assets/scrappers/`. */
  logo: string;
  /** Brand background tint when the logo needs one to read on the chip
   * (LaunchBox ships a white isotype that disappears on a light chip). */
  bg?: string;
}

export const METADATA_PROVIDERS: readonly MetadataProvider[] = [
  {
    key: "hasheous_id",
    name: "Hasheous",
    title: "Verified with Hasheous",
    logo: "hasheous.png",
  },
  { key: "igdb_id", name: "IGDB", title: "IGDB match", logo: "igdb.png" },
  {
    key: "ss_id",
    name: "ScreenScraper",
    title: "ScreenScraper match",
    logo: "ss.png",
  },
  {
    key: "moby_id",
    name: "MobyGames",
    title: "MobyGames match",
    logo: "moby.png",
  },
  {
    key: "launchbox_id",
    name: "LaunchBox",
    title: "LaunchBox match",
    logo: "launchbox.png",
    bg: "#185a7c",
  },
  {
    key: "ra_id",
    name: "RetroAchievements",
    title: "RetroAchievements match",
    logo: "ra.png",
  },
  {
    key: "flashpoint_id",
    name: "Flashpoint",
    title: "Flashpoint match",
    logo: "flashpoint.png",
  },
  {
    key: "hltb_id",
    name: "HowLongToBeat",
    title: "HowLongToBeat match",
    logo: "hltb.png",
  },
  { key: "gamelist_id", name: "ES-DE", title: "ES-DE match", logo: "esde.png" },
  {
    key: "libretro_id",
    name: "Libretro",
    title: "Libretro match",
    logo: "libretro.png",
  },
];

/** Filter slug (matching the backend MetadataSource) for a provider id key. */
function providerSlug(key: ProviderIdKey): string {
  return key.replace(/_id$/, "");
}

/** Options for the gallery "metadata provider" filter, derived from the
 * registry so it stays the single source of truth. `value` is the slug the
 * backend filter expects; `title` is the brand name. */
export const METADATA_PROVIDER_FILTER_OPTIONS: {
  value: string;
  title: string;
}[] = METADATA_PROVIDERS.map((p) => ({
  value: providerSlug(p.key),
  title: p.name,
}));

/** Returns the providers whose id field is populated on the given ROM. */
export function activeProviders(rom: SimpleRom): MetadataProvider[] {
  return METADATA_PROVIDERS.filter((p) => Boolean(rom[p.key]));
}
