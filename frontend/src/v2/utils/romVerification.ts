// "Verified" means the ROM's hash matched a known database (via Hasheous or
// the RA hash list). Mirrors the backend's `_filter_by_verified`.
import type { RomHasheousMetadata } from "@/__generated__";
import type { SimpleRom } from "@/stores/roms";

type Matcher = (rom: SimpleRom) => boolean;

function hasheous(...keys: (keyof RomHasheousMetadata)[]): Matcher {
  return (rom) => keys.some((key) => Boolean(rom.hasheous_metadata?.[key]));
}

// Each database this ROM's hash can be checked against. MAME reports Arcade
// and MESS separately, and Redump reports disc images and their CHD
// conversions separately; either flag counts. Order is the display order for
// the Metadata tab chips.
export const VERIFICATION_DATABASES: { label: string; matches: Matcher }[] = [
  { label: "TOSEC", matches: hasheous("tosec_match") },
  { label: "No-Intro", matches: hasheous("nointro_match") },
  { label: "Redump", matches: hasheous("redump_match", "mame_redump_match") },
  { label: "MAME", matches: hasheous("mame_arcade_match", "mame_mess_match") },
  { label: "FBNeo", matches: hasheous("fbneo_match") },
  { label: "WHDLoad", matches: hasheous("whdload_match") },
  { label: "PureDOS", matches: hasheous("puredos_match") },
  {
    label: "RetroAchievements",
    // RA hashes only part of some ROMs (NDS, PSP), which Hasheous can't match.
    matches: (rom) =>
      hasheous("ra_match")(rom) || Boolean(rom.merged_ra_metadata?.hash_match),
  },
];

// Whether the ROM is verified against any known database.
export function isRomVerified(rom: SimpleRom): boolean {
  return VERIFICATION_DATABASES.some((db) => db.matches(rom));
}
