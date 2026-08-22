import { describe, expect, it } from "vitest";
import {
  ALL_DISCS,
  bootDiscId,
  defaultDisc,
  resolveStoredDisc,
} from "./playerDisc";

// Only `id` and `file_name` are read off each file; minimal stubs stand in for
// RomFileSchema. Ids default to a `.chd` name, which is not a playlist.
const files = (...ids: number[]) =>
  ids.map((id) => ({ id, file_name: `Game (Disc ${id}).chd` }));
const withM3u = (...ids: number[]) => [
  ...files(...ids),
  { id: 99, file_name: "Game.m3u" },
];

describe("resolveStoredDisc", () => {
  it("keeps a stored id that still belongs to the rom", () => {
    expect(resolveStoredDisc("2", files(1, 2, 3))).toEqual({
      disc: 2,
      stale: false,
    });
  });

  it("falls back to the first file and marks stale when the id is gone", () => {
    // Classic post-rescan case: files were reimported with new ids.
    expect(resolveStoredDisc("2", files(10, 11, 12))).toEqual({
      disc: 10,
      stale: true,
    });
  });

  it("falls back to the first file without staleness when nothing was stored", () => {
    expect(resolveStoredDisc(null, files(5, 6))).toEqual({
      disc: 5,
      stale: false,
    });
  });

  it("treats a non-numeric stored value as stale garbage to forget", () => {
    expect(resolveStoredDisc("not-a-number", files(1))).toEqual({
      disc: 1,
      stale: true,
    });
  });

  it("returns a null disc (and no staleness) for a rom with no files", () => {
    expect(resolveStoredDisc(null, [])).toEqual({
      disc: null,
      stale: false,
    });
  });

  it("still clears a stored id when the rom now has no files", () => {
    expect(resolveStoredDisc("2", [])).toEqual({
      disc: null,
      stale: true,
    });
  });

  it("keeps a stored all-discs choice while the rom is multi-file", () => {
    expect(resolveStoredDisc(ALL_DISCS, files(1, 2))).toEqual({
      disc: ALL_DISCS,
      stale: false,
    });
  });

  it("drops a stored all-discs choice once the rom is single-file", () => {
    expect(resolveStoredDisc(ALL_DISCS, files(7))).toEqual({
      disc: 7,
      stale: true,
    });
  });
});

describe("defaultDisc", () => {
  it("boots every file together when the set ships its own playlist", () => {
    expect(defaultDisc(withM3u(1, 2))).toBe(ALL_DISCS);
  });

  it("matches the playlist extension case-insensitively", () => {
    expect(
      defaultDisc([
        { id: 1, file_name: "Game (Disc 1).chd" },
        { id: 2, file_name: "Game.M3U" },
      ]),
    ).toBe(ALL_DISCS);
  });

  it("boots the first file when a multi-file set has no playlist", () => {
    expect(defaultDisc(files(3, 4))).toBe(3);
  });

  it("boots the only file of a single-file rom carrying a playlist", () => {
    expect(defaultDisc([{ id: 1, file_name: "Game.m3u" }])).toBe(1);
  });

  it("returns null for a rom with no files", () => {
    expect(defaultDisc([])).toBeNull();
  });
});

describe("bootDiscId", () => {
  it("downloads a single file when one disc is selected", () => {
    expect(bootDiscId(4)).toBe(4);
  });

  it("downloads the rom whole for all-discs and for no selection", () => {
    expect(bootDiscId(ALL_DISCS)).toBeNull();
    expect(bootDiscId(null)).toBeNull();
  });
});
