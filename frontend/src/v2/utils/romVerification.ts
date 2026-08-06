// romVerification: single source of truth for what "verified" means, i.e.
// a ROM whose file hash matched a known ROM database. Mirrors the backend's
// `_filter_by_verified` (roms_handler.py) so the header badge, the
// per-database chips in the Metadata tab, and the library "verified"
// filter all agree. Merely having a computed hash (crc/md5/sha1) does
// NOT make a ROM verified.
import type { RomHasheousMetadata } from "@/__generated__";
import type { SimpleRom } from "@/stores/roms";

// Whether any of the given Hasheous flags is set. Hasheous reports, per
// submitted hash, the signature sources that hash was found in, so these
// are per-file. MAME reports Arcade and MESS separately; Redump likewise
// reports disc images and their CHD conversions separately. Either flag
// counts as a hit for that database.
export function matchesDatabase(
  rom: SimpleRom,
  keys: (keyof RomHasheousMetadata)[],
): boolean {
  const h = rom.hasheous_metadata;
  if (!h) return false;
  return keys.some((key) => Boolean(h[key]));
}

// RetroAchievements is the one database RomM asks directly, and its own
// answer wins: `ra_hash_match` comes from RA's hash list, which is what
// decides whether achievements unlock, while Hasheous knows RA's dumps
// only as far as its signature coverage reaches. So a definite `false`
// from RA is trusted over a Hasheous hit, since falling back there would
// promise achievements for a file RA has never seen. `null` means RA was
// never asked (platform it doesn't cover, or a ROM not rescanned since
// the column landed), and only then does Hasheous answer.
function matchesRetroAchievements(rom: SimpleRom): boolean {
  if (rom.ra_hash_match != null) return rom.ra_hash_match;
  return matchesDatabase(rom, ["ra_match"]);
}

// Order is the display order for the Metadata tab chips.
export const VERIFICATION_DATABASES: {
  label: string;
  matches: (rom: SimpleRom) => boolean;
}[] = [
  { label: "TOSEC", matches: (r) => matchesDatabase(r, ["tosec_match"]) },
  { label: "No-Intro", matches: (r) => matchesDatabase(r, ["nointro_match"]) },
  {
    label: "Redump",
    matches: (r) => matchesDatabase(r, ["redump_match", "mame_redump_match"]),
  },
  {
    label: "MAME",
    matches: (r) =>
      matchesDatabase(r, ["mame_arcade_match", "mame_mess_match"]),
  },
  { label: "FBNeo", matches: (r) => matchesDatabase(r, ["fbneo_match"]) },
  { label: "WHDLoad", matches: (r) => matchesDatabase(r, ["whdload_match"]) },
  { label: "PureDOS", matches: (r) => matchesDatabase(r, ["puredos_match"]) },
  { label: "RetroAchievements", matches: matchesRetroAchievements },
];

// Whether the ROM is verified against any known database.
export function isRomVerified(rom: SimpleRom): boolean {
  return VERIFICATION_DATABASES.some((db) => db.matches(rom));
}
