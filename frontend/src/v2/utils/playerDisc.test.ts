import { beforeEach, describe, expect, it } from "vitest";
import type { RomFileCategory } from "@/__generated__";
import {
  ALL_DISCS,
  bootDiscId,
  bootableFiles,
  defaultDisc,
  rememberDisc,
  resolveRememberedDisc,
  resolveStoredDisc,
} from "./playerDisc";

// Only `id`, `file_name` and `category` are read off each file; minimal stubs
// stand in for RomFileSchema.
const file = (
  id: number,
  file_name: string,
  category: RomFileCategory | null = null,
) => ({ id, file_name, category });

const files = (...ids: number[]) =>
  ids.map((id) => file(id, `Game (Disc ${id}).chd`));

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
    expect(defaultDisc([...files(1, 2), file(99, "Game.m3u")])).toBe(ALL_DISCS);
  });

  it("matches the playlist extension case-insensitively", () => {
    expect(
      defaultDisc([file(1, "Game (Disc 1).chd"), file(2, "Game.M3U")]),
    ).toBe(ALL_DISCS);
  });

  it("boots the first file when a multi-file set has no playlist", () => {
    expect(defaultDisc(files(3, 4))).toBe(3);
  });

  it("boots the only file of a single-file rom carrying a playlist", () => {
    expect(defaultDisc([file(1, "Game.m3u")])).toBe(1);
  });

  it("returns null for a rom with no files", () => {
    expect(defaultDisc([])).toBeNull();
  });

  it("skips media that sorts before the game file", () => {
    expect(
      defaultDisc([
        file(1, "artwork.png", "screenshot"),
        file(2, "Game.chd", "game"),
      ]),
    ).toBe(2);
  });

  it("still boots a file scanned before categories existed", () => {
    expect(defaultDisc([file(1, "Game.chd", null)])).toBe(1);
  });

  it("boots media rather than nothing when that is all the rom has", () => {
    expect(defaultDisc([file(1, "manual.pdf", "manual")])).toBe(1);
  });
});

describe("bootableFiles", () => {
  it("drops every category a core cannot boot", () => {
    const game = file(1, "Game.chd", "game");

    expect(
      bootableFiles([
        file(2, "manual.pdf", "manual"),
        file(3, "guide.txt", "walkthrough"),
        file(4, "shot.png", "screenshot"),
        file(5, "track.mp3", "soundtrack"),
        file(6, "fix.ips", "patch"),
        file(7, "codes.cht", "cheat"),
        game,
      ]),
    ).toEqual([game]);
  });

  it("keeps the parts of a multi-file release", () => {
    const release = [
      file(1, "Game.nsp", "game"),
      file(2, "Game.nsz", "update"),
      file(3, "Game DLC.nsp", "dlc"),
    ];

    expect(bootableFiles(release)).toEqual(release);
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

describe("rememberDisc / resolveRememberedDisc", () => {
  const ROM_ID = 42;
  beforeEach(() => localStorage.clear());

  it("round-trips a whole-set boot", () => {
    rememberDisc(ROM_ID, ALL_DISCS);
    expect(resolveRememberedDisc(ROM_ID, files(1, 2))).toBe(ALL_DISCS);
  });

  it("round-trips a single disc", () => {
    rememberDisc(ROM_ID, 2);
    expect(resolveRememberedDisc(ROM_ID, files(1, 2))).toBe(2);
  });

  it("forgets the choice when there is nothing to boot", () => {
    rememberDisc(ROM_ID, 2);
    rememberDisc(ROM_ID, null);
    expect(resolveRememberedDisc(ROM_ID, files(5, 6))).toBe(5);
  });

  it("drops a stale entry rather than leaving it to 404 the download", () => {
    rememberDisc(ROM_ID, 2);
    expect(resolveRememberedDisc(ROM_ID, files(10, 11))).toBe(10);
    expect(localStorage.getItem(`player:${ROM_ID}:disc-selection`)).toBeNull();
  });

  it("survives the v1 player clearing its own key on a whole-set boot", () => {
    rememberDisc(ROM_ID, ALL_DISCS);
    // What v1's <Player> does on mount when handed a null disc.
    localStorage.removeItem(`player:${ROM_ID}:disc`);
    expect(resolveRememberedDisc(ROM_ID, files(1, 2))).toBe(ALL_DISCS);
  });

  it("seeds from a disc the user last picked in the v1 player", () => {
    localStorage.setItem(`player:${ROM_ID}:disc`, "2");
    expect(resolveRememberedDisc(ROM_ID, files(1, 2))).toBe(2);
  });

  it("prefers its own choice over a stale v1 one", () => {
    localStorage.setItem(`player:${ROM_ID}:disc`, "2");
    rememberDisc(ROM_ID, ALL_DISCS);
    expect(resolveRememberedDisc(ROM_ID, files(1, 2))).toBe(ALL_DISCS);
  });

  it("keeps each game's choice separate", () => {
    rememberDisc(ROM_ID, 2);
    expect(resolveRememberedDisc(99, files(1, 2))).toBe(1);
  });

  it("drops a remembered media file once the caller filters media out", () => {
    const bootable = bootableFiles([
      file(1, "manual.pdf", "manual"),
      file(2, "Game.chd", "game"),
    ]);
    rememberDisc(ROM_ID, 1);

    expect(resolveRememberedDisc(ROM_ID, bootable)).toBe(2);
    expect(localStorage.getItem(`player:${ROM_ID}:disc-selection`)).toBeNull();
  });
});
