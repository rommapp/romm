import { beforeEach, describe, expect, it } from "vitest";
import type { RomFileCategory } from "@/__generated__";
import {
  ALL_DISCS,
  bootDiscId,
  bootFileIds,
  bootableFiles,
  defaultDisc,
  offersAllDiscs,
  rememberDisc,
  resolveRememberedDisc,
  resolveStoredDisc,
  selectableDiscFiles,
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

  it.each(["cue", "gdi", "ccd", "mds", "CUE"])(
    "boots every file together when the set has a .%s sheet",
    (extension) => {
      expect(
        defaultDisc([
          file(1, `Game.${extension}`),
          file(2, "Game (Track 1).bin"),
          file(3, "Game (Track 2).bin"),
        ]),
      ).toBe(ALL_DISCS);
    },
  );

  it("boots a lone sheet when it is the rom's only file", () => {
    expect(defaultDisc([file(1, "Game.cue")])).toBe(1);
  });

  it("keeps a remembered track over the sheet default", () => {
    const cueSet = [file(1, "Game.cue"), file(2, "Game.iso")];
    expect(resolveStoredDisc("2", cueSet)).toEqual({ disc: 2, stale: false });
    expect(resolveStoredDisc(null, cueSet)).toEqual({
      disc: ALL_DISCS,
      stale: false,
    });
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

describe("selectableDiscFiles", () => {
  // Handing a core the playlist alone gives it a file list of one text file.
  it("drops the playlist, which only names the discs beside it", () => {
    const disc1 = file(1, "Game (Disk 1 of 2).adf");
    const disc2 = file(2, "Game (Disk 2 of 2).adf");
    const playlist = file(3, "Game.m3u");

    expect(selectableDiscFiles([disc1, disc2, playlist])).toEqual([
      disc1,
      disc2,
    ]);
  });

  it("matches the playlist extension case-insensitively", () => {
    expect(
      selectableDiscFiles([file(1, "Game.chd"), file(2, "Game.M3U")]),
    ).toEqual([file(1, "Game.chd")]);
  });

  it("still drops what a core cannot boot", () => {
    const rom = file(1, "Game.chd");
    expect(selectableDiscFiles([rom, file(2, "guide.pdf", "manual")])).toEqual([
      rom,
    ]);
  });
});

describe("resolveStoredDisc with a remembered playlist", () => {
  it("boots the set whole instead of the playlist on its own", () => {
    const stored = resolveStoredDisc("3", [
      file(1, "Game (Disk 1 of 2).adf"),
      file(2, "Game (Disk 2 of 2).adf"),
      file(3, "Game.m3u"),
    ]);

    expect(stored).toEqual({ disc: ALL_DISCS, stale: true });
  });
});

// Issue #5462: variants in translations/ or hacks/ sit beside the base game.
describe("a rom with translated or hacked variants", () => {
  const disc1 = file(1, "Parasite Eve (USA) (Disc 1).chd");
  const disc2 = file(2, "Parasite Eve (USA) (Disc 2).chd");
  const playlist = file(3, "Parasite Eve (USA).m3u");
  const tDisc1 = file(
    4,
    "Parasite Eve (USA) (Disc 1) (T-Es).chd",
    "translation",
  );
  const tDisc2 = file(
    5,
    "Parasite Eve (USA) (Disc 2) (T-Es).chd",
    "translation",
  );
  const tPlaylist = file(6, "Parasite Eve (USA) (T-Es).m3u", "translation");
  const multiDisc = [tDisc1, tDisc2, tPlaylist, disc1, disc2, playlist];

  const cartridge = file(10, "Mother 3 (Japan).gba");
  const upsPatch = file(11, "Mother 3 (Japan) (T-Es).ups", "translation");
  const bpsPatch = file(12, "Mother 3 (Japan) (T-Es).BPS", "translation");

  const hacked = file(20, "Game (Hack).gba", "hack");
  const plain = file(21, "Game.gba");

  it("never boots a patch file, whatever folder it sits in", () => {
    expect(bootableFiles([upsPatch, bpsPatch, cartridge])).toEqual([cartridge]);
    expect(defaultDisc([upsPatch, bpsPatch, cartridge])).toBe(10);
  });

  it("defaults to the base game's set, not a variant's playlist", () => {
    expect(defaultDisc(multiDisc)).toBe(ALL_DISCS);
  });

  it("defaults to the base file when a variant sorts before it", () => {
    expect(defaultDisc([hacked, plain])).toBe(21);
  });

  it("lists the base game's discs before the variants", () => {
    expect(selectableDiscFiles(multiDisc)).toEqual([
      disc1,
      disc2,
      tDisc1,
      tDisc2,
    ]);
  });

  it("offers all discs only when the base game has several", () => {
    expect(offersAllDiscs(multiDisc)).toBe(true);
    expect(offersAllDiscs([hacked, plain])).toBe(false);
  });

  it("drops a stored all-discs choice once the base game is one file", () => {
    expect(resolveStoredDisc(ALL_DISCS, [hacked, plain])).toEqual({
      disc: 21,
      stale: true,
    });
  });

  it("boots all discs as the base set alone", () => {
    expect(bootFileIds(ALL_DISCS, multiDisc)).toEqual([1, 2, 3]);
  });
});

describe("bootFileIds", () => {
  it("downloads a single file when one disc is selected", () => {
    expect(bootFileIds(4, files(4, 5))).toEqual([4]);
  });

  it("downloads the rom whole when every file is the base game", () => {
    expect(bootFileIds(ALL_DISCS, files(1, 2))).toEqual([]);
    expect(bootFileIds(null, files(1, 2))).toEqual([]);
  });

  it("leaves media out of an all-discs boot", () => {
    expect(
      bootFileIds(ALL_DISCS, [...files(1, 2), file(3, "manual.pdf", "manual")]),
    ).toEqual([1, 2]);
  });

  it("downloads the rom whole when it is nothing but variants", () => {
    expect(
      bootFileIds(ALL_DISCS, [
        file(1, "Game (Disc 1).chd", "hack"),
        file(2, "Game (Disc 2).chd", "hack"),
      ]),
    ).toEqual([]);
  });
});
