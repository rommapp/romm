import { describe, expect, it } from "vitest";
import type { RomHasheousMetadata } from "@/__generated__";
import type { SimpleRom } from "@/stores/roms";
import {
  isRomVerified,
  matchesDatabase,
  VERIFICATION_DATABASES,
} from "./romVerification";

// Only `hasheous_metadata` and `ra_hash_match` are read; cast a minimal
// stub to SimpleRom.
const rom = (
  hasheous_metadata?: RomHasheousMetadata | null,
  ra_hash_match: boolean | null = null,
): SimpleRom => ({ hasheous_metadata, ra_hash_match }) as SimpleRom;

const db = (label: string) =>
  VERIFICATION_DATABASES.find((d) => d.label === label)!;

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
    const keys: (keyof RomHasheousMetadata)[] = [
      "tosec_match",
      "nointro_match",
      "redump_match",
      "mame_redump_match",
      "mame_arcade_match",
      "mame_mess_match",
      "fbneo_match",
      "whdload_match",
      "puredos_match",
      "ra_match",
    ];
    for (const key of keys) {
      expect(isRomVerified(rom({ [key]: true }))).toBe(true);
    }
  });

  it("is true on RA's own hash match alone, with no hasheous metadata", () => {
    expect(isRomVerified(rom(null, true))).toBe(true);
  });
});

describe("matchesDatabase", () => {
  it("matches MAME on either the arcade or the mess flag", () => {
    const mame = db("MAME");
    expect(mame.matches(rom())).toBe(false);
    expect(mame.matches(rom({ mame_arcade_match: true }))).toBe(true);
    expect(mame.matches(rom({ mame_mess_match: true }))).toBe(true);
  });

  it("matches Redump on either the disc-image or the CHD flag", () => {
    const redump = db("Redump");
    expect(redump.matches(rom({ redump_match: true }))).toBe(true);
    // Hasheous indexes CHD conversions under its own MAMERedump source.
    expect(redump.matches(rom({ mame_redump_match: true }))).toBe(true);
  });

  it("still reads raw hasheous flags for callers that pass keys", () => {
    expect(matchesDatabase(rom({ tosec_match: true }), ["tosec_match"])).toBe(
      true,
    );
    expect(matchesDatabase(rom(), ["tosec_match"])).toBe(false);
  });
});

// RA is the one database RomM asks directly. Achievements unlock on RA's
// own hash list, so that answer outranks Hasheous' narrower RA signature
// coverage in both directions.
describe("RetroAchievements verification", () => {
  const ra = () => db("RetroAchievements");

  it("matches when RA's own hash list knows the file", () => {
    expect(ra().matches(rom(null, true))).toBe(true);
  });

  it("falls back to hasheous when RA was never asked", () => {
    expect(ra().matches(rom({ ra_match: true }, null))).toBe(true);
    expect(ra().matches(rom({ ra_match: false }, null))).toBe(false);
    expect(ra().matches(rom(null, null))).toBe(false);
  });

  it("trusts RA over hasheous when the two disagree", () => {
    // RA knows the dump, hasheous' RA signatures don't reach it: the case
    // that had users seeing a grey tag next to a working RA match.
    expect(ra().matches(rom({ ra_match: false }, true))).toBe(true);
    // RA has never seen the dump: don't promise achievements.
    expect(ra().matches(rom({ ra_match: true }, false))).toBe(false);
  });

  it("does not read ra_id", () => {
    // `ra_id` is the game, so every sibling shares it.
    const withGameId = { hasheous_metadata: null, ra_id: 12345 } as SimpleRom;
    expect(ra().matches(withGameId)).toBe(false);
  });
});
