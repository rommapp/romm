import { describe, expect, it } from "vitest";
import type { RomHasheousMetadata } from "@/__generated__";
import type { SimpleRom } from "@/stores/roms";
import {
  isRomVerified,
  matchesDatabase,
  VERIFICATION_DATABASES,
  VERIFICATION_KEYS,
} from "./romVerification";

// Only `hasheous_metadata` is read; cast a minimal stub to SimpleRom.
const rom = (hasheous_metadata?: RomHasheousMetadata | null): SimpleRom =>
  ({ hasheous_metadata }) as SimpleRom;

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

  it("treats RetroAchievements as a database match (ra_match, not ra_id)", () => {
    const ra = VERIFICATION_DATABASES.find(
      (db) => db.label === "RetroAchievements",
    )!;
    expect(ra.keys).toEqual(["ra_match"]);
    expect(matchesDatabase(rom({ ra_match: true }), ra.keys)).toBe(true);
  });
});

describe("VERIFICATION_KEYS", () => {
  it("is the flattened set of every database's match flags", () => {
    expect(VERIFICATION_KEYS).toEqual(
      VERIFICATION_DATABASES.flatMap((db) => db.keys),
    );
  });
});
