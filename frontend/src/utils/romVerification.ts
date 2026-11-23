// "Verified" means the ROM's hash matched a known database (via Hasheous or
// the RA hash list). Mirrors the backend's `_filter_by_verified`.
import type { RomHasheousMetadata } from "@/__generated__";
import type { SimpleRom } from "@/stores/roms";

type Matcher = (rom: SimpleRom) => boolean;

function anyHasheousFlag(...keys: (keyof RomHasheousMetadata)[]): Matcher {
  return (rom) => keys.some((key) => Boolean(rom.hasheous_metadata?.[key]));
}

// MAME (arcade/MESS) and Redump (disc/CHD) each report two flags; either counts.
// Order is the display order for the Metadata tab chips.
export const VERIFICATION_DATABASES: { label: string; matches: Matcher }[] = [
  { label: "TOSEC", matches: anyHasheousFlag("tosec_match") },
  { label: "No-Intro", matches: anyHasheousFlag("nointro_match") },
  {
    label: "Redump",
    matches: anyHasheousFlag("redump_match", "mame_redump_match"),
  },
  {
    label: "MAME",
    matches: anyHasheousFlag("mame_arcade_match", "mame_mess_match"),
  },
  { label: "FBNeo", matches: anyHasheousFlag("fbneo_match") },
  { label: "WHDLoad", matches: anyHasheousFlag("whdload_match") },
  { label: "PureDOS", matches: anyHasheousFlag("puredos_match") },
  {
    label: "RetroAchievements",
    // RA hashes only part of some ROMs (NDS, PSP), which Hasheous can't match.
    matches: (rom) =>
      anyHasheousFlag("ra_match")(rom) ||
      Boolean(rom.merged_ra_metadata?.hash_match),
  },
];

// Whether the ROM is verified against any known database.
export function isRomVerified(rom: SimpleRom): boolean {
  return VERIFICATION_DATABASES.some((db) => db.matches(rom));
}
