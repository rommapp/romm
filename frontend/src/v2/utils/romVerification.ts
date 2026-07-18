// romVerification — single source of truth for what "verified" means: a
// ROM whose file hash matched a known ROM database (via Hasheous). Mirrors
// the backend's `_filter_by_verified` (roms_handler.py) so the header
// badge, the per-database chips in the Metadata tab, and the library
// "verified" filter all agree. Merely having a computed hash
// (crc/md5/sha1) does NOT make a ROM verified.
import type { RomHasheousMetadata } from "@/__generated__";
import type { SimpleRom } from "@/stores/roms";

// Each database this ROM's hash can be checked against, with the Hasheous
// match flag(s) that count as a hit. MAME reports Arcade and MESS
// separately; either one means the ROM matched MAME. Order is the display
// order for the Metadata tab chips.
export const VERIFICATION_DATABASES: {
  label: string;
  keys: (keyof RomHasheousMetadata)[];
}[] = [
  { label: "TOSEC", keys: ["tosec_match"] },
  { label: "No-Intro", keys: ["nointro_match"] },
  { label: "Redump", keys: ["redump_match"] },
  { label: "MAME", keys: ["mame_arcade_match", "mame_mess_match"] },
  { label: "FBNeo", keys: ["fbneo_match"] },
  { label: "WHDLoad", keys: ["whdload_match"] },
  { label: "PureDOS", keys: ["puredos_match"] },
  { label: "RetroAchievements", keys: ["ra_match"] },
];

// Flattened match flags, i.e. the exact set the backend filters on.
export const VERIFICATION_KEYS: (keyof RomHasheousMetadata)[] =
  VERIFICATION_DATABASES.flatMap((db) => db.keys);

// Whether a single database matched for this ROM.
export function matchesDatabase(
  rom: SimpleRom,
  keys: (keyof RomHasheousMetadata)[],
): boolean {
  const h = rom.hasheous_metadata;
  if (!h) return false;
  return keys.some((key) => Boolean(h[key]));
}

// Whether the ROM is verified against any known database.
export function isRomVerified(rom: SimpleRom): boolean {
  return matchesDatabase(rom, VERIFICATION_KEYS);
}
