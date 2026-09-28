import { describe, expect, it } from "vitest";
import type { RomHasheousMetadata, RomRAMetadata } from "@/__generated__";
import type { SimpleRom } from "@/stores/roms";
import { rom as listRom } from "@/v2/components/Gallery/listRowFixture";
import { isRomVerified, VERIFICATION_DATABASES } from "./romVerification";

const rom = (
  hasheous_metadata: RomHasheousMetadata | null = null,
  merged_ra_metadata: RomRAMetadata | null = null,
): SimpleRom => listRom({ hasheous_metadata, merged_ra_metadata });

const database = (label: string) =>
  VERIFICATION_DATABASES.find((db) => db.label === label)!;

// Every Hasheous flag the backend's `_filter_by_verified` counts.
const HASHEOUS_KEYS: (keyof RomHasheousMetadata)[] = [
  "tosec_match",
  "mame_arcade_match",
  "mame_mess_match",
  "nointro_match",
  "redump_match",
  "mame_redump_match",
  "whdload_match",
  "ra_match",
  "fbneo_match",
  "puredos_match",
];

describe("isRomVerified", () => {
  it("is false when there is no hasheous metadata", () => {
    expect(isRomVerified(rom())).toBe(false);
    expect(isRomVerified(rom(null))).toBe(false);
  });

  it("is false when no signature matched (e.g. a hashed-but-unmatched archive)", () => {
    expect(
      isRomVerified(
        rom({ tosec_match: false, nointro_match: false, ra_match: false }),
      ),
    ).toBe(false);
  });

  it("is true when any single database matched", () => {
    for (const key of HASHEOUS_KEYS) {
      expect(isRomVerified(rom({ [key]: true }))).toBe(true);
    }
  });

  it("is true for an RA hash match alone", () => {
    expect(isRomVerified(rom(null, { hash_match: true }))).toBe(true);
    expect(isRomVerified(rom(null, { hash_match: false }))).toBe(false);
  });
});

describe("VERIFICATION_DATABASES", () => {
  it("matches MAME on either the arcade or the mess flag", () => {
    const mame = database("MAME");
    expect(mame.matches(rom())).toBe(false);
    expect(mame.matches(rom({ mame_arcade_match: true }))).toBe(true);
    expect(mame.matches(rom({ mame_mess_match: true }))).toBe(true);
  });

  it("matches Redump on either the disc-image or the CHD flag", () => {
    const redump = database("Redump");
    expect(redump.matches(rom({ redump_match: true }))).toBe(true);
    // Hasheous indexes CHD conversions under its own MAMERedump source.
    expect(redump.matches(rom({ mame_redump_match: true }))).toBe(true);
  });

  it("matches RetroAchievements on Hasheous' flag or the RA hash match", () => {
    const ra = database("RetroAchievements");
    expect(ra.matches(rom({ ra_match: true }))).toBe(true);
    expect(ra.matches(rom({ ra_match: false }, { hash_match: true }))).toBe(
      true,
    );
    expect(ra.matches(rom(null, { hash_match: false }))).toBe(false);
  });

  it("does not credit an RA hash match to other databases", () => {
    const raHashMatch = rom(null, { hash_match: true });
    for (const db of VERIFICATION_DATABASES) {
      if (db.label === "RetroAchievements") continue;
      expect(db.matches(raHashMatch)).toBe(false);
    }
  });
});
