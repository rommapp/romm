import { describe, expect, it } from "vitest";
import type { RomHasheousMetadata, RomRAMetadata } from "@/__generated__";
import type { SimpleRom } from "@/stores/roms";
import {
  isRomVerified,
  matchesDatabase,
  VERIFICATION_DATABASES,
  VERIFICATION_KEYS,
} from "./romVerification";

// Only the match blobs are read; cast a minimal stub to SimpleRom.
const rom = (
  hasheous_metadata?: RomHasheousMetadata | null,
  merged_ra_metadata?: RomRAMetadata | null,
): SimpleRom => ({ hasheous_metadata, merged_ra_metadata }) as SimpleRom;

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
    for (const key of VERIFICATION_KEYS) {
      expect(isRomVerified(rom({ [key]: true }))).toBe(true);
    }
  });
});

describe("matchesDatabase", () => {
  it("matches MAME on either the arcade or the mess flag", () => {
    const mame = VERIFICATION_DATABASES.find((db) => db.label === "MAME")!;
    expect(matchesDatabase(rom(), mame.keys)).toBe(false);
    expect(matchesDatabase(rom({ mame_arcade_match: true }), mame.keys)).toBe(
      true,
    );
    expect(matchesDatabase(rom({ mame_mess_match: true }), mame.keys)).toBe(
      true,
    );
  });

  it("matches Redump on either the disc-image or the CHD flag", () => {
    const redump = VERIFICATION_DATABASES.find((db) => db.label === "Redump")!;
    expect(matchesDatabase(rom({ redump_match: true }), redump.keys)).toBe(
      true,
    );
    // Hasheous indexes CHD conversions under its own MAMERedump source.
    expect(matchesDatabase(rom({ mame_redump_match: true }), redump.keys)).toBe(
      true,
    );
  });

  it("treats RetroAchievements as a database match (ra_match, not ra_id)", () => {
    const ra = VERIFICATION_DATABASES.find(
      (db) => db.label === "RetroAchievements",
    )!;
    expect(ra.keys).toEqual(["ra_match"]);
    expect(matchesDatabase(rom({ ra_match: true }), ra.keys)).toBe(true);
  });

  it("counts a scan-time RA hash match when Hasheous has no RA flag", () => {
    const ra = VERIFICATION_DATABASES.find(
      (db) => db.label === "RetroAchievements",
    )!;
    const raHashMatch = rom({ ra_match: false }, { hash_match: true });
    expect(matchesDatabase(raHashMatch, ra.keys)).toBe(true);
    expect(matchesDatabase(rom(null, { hash_match: true }), ra.keys)).toBe(
      true,
    );
    expect(matchesDatabase(rom(null, { hash_match: false }), ra.keys)).toBe(
      false,
    );
  });

  it("does not credit an RA hash match to other databases", () => {
    const raHashMatch = rom(null, { hash_match: true });
    for (const db of VERIFICATION_DATABASES) {
      if (db.label === "RetroAchievements") continue;
      expect(matchesDatabase(raHashMatch, db.keys)).toBe(false);
    }
    expect(isRomVerified(raHashMatch)).toBe(true);
  });
});

describe("VERIFICATION_KEYS", () => {
  it("is the flattened set of every database's match flags", () => {
    expect(VERIFICATION_KEYS).toEqual(
      VERIFICATION_DATABASES.flatMap((db) => db.keys),
    );
  });
});
