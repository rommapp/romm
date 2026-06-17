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
  /** Tooltip text — also serves as the chip's `alt`. */
  title: string;
  /** File under `/assets/scrappers/`. */
  logo: string;
  /** Brand background tint when the logo needs one to read on the chip
   * (LaunchBox ships a white isotype that disappears on a light chip). */
  bg?: string;
}

export const METADATA_PROVIDERS: readonly MetadataProvider[] = [
  { key: "hasheous_id", title: "Verified with Hasheous", logo: "hasheous.png" },
  { key: "igdb_id", title: "IGDB match", logo: "igdb.png" },
  { key: "ss_id", title: "ScreenScraper match", logo: "ss.png" },
  { key: "moby_id", title: "MobyGames match", logo: "moby.png" },
  {
    key: "launchbox_id",
    title: "LaunchBox match",
    logo: "launchbox.png",
    bg: "#185a7c",
  },
  { key: "ra_id", title: "RetroAchievements match", logo: "ra.png" },
  { key: "flashpoint_id", title: "Flashpoint match", logo: "flashpoint.png" },
  { key: "hltb_id", title: "HowLongToBeat match", logo: "hltb.png" },
  { key: "gamelist_id", title: "ES-DE match", logo: "esde.png" },
  { key: "libretro_id", title: "Libretro match", logo: "libretro.png" },
];

/** Returns the providers whose id field is populated on the given ROM. */
export function activeProviders(rom: SimpleRom): MetadataProvider[] {
  return METADATA_PROVIDERS.filter((p) => Boolean(rom[p.key]));
}
