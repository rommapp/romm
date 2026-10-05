import { describe, expect, it } from "vitest";
import {
  getDownloadFileName,
  getDownloadLink,
  getDownloadPath,
  getSoleRomFile,
} from "./downloadPath";
import { romFileFixture, romFixture } from "./rom.fixtures";

describe("getDownloadPath", () => {
  it("uses fs_name for a flat single-file rom", () => {
    const rom = romFixture({
      id: 14,
      fs_name: "Maniac Mansion (1989).adf",
      has_nested_single_file: false,
      files: [
        romFileFixture({ id: 19, file_name: "Maniac Mansion (1989).adf" }),
      ],
    });
    expect(getDownloadPath({ rom })).toBe(
      "/api/roms/14/content/Maniac%20Mansion%20(1989).adf",
    );
  });

  it("uses the file name for a nested single-file rom", () => {
    const rom = romFixture({
      id: 21,
      fs_name: "Art Of Fighting",
      has_nested_single_file: true,
      files: [romFileFixture({ id: 26, file_name: "aof.zip" })],
    });
    expect(getDownloadPath({ rom })).toBe("/api/roms/21/content/aof.zip");
  });

  it("uses fs_name for an unselected multi-file rom", () => {
    const rom = romFixture({
      id: 24,
      fs_name: "B.A.T.",
      has_nested_single_file: false,
      files: [
        romFileFixture({ id: 29, file_name: "B.A.T. Disk1.adf" }),
        romFileFixture({ id: 30, file_name: "B.A.T. Disk2.adf" }),
      ],
    });
    expect(getDownloadPath({ rom })).toBe("/api/roms/24/content/B.A.T.");
  });

  it("uses the selected file name (with extension) for a single file", () => {
    // fs_name is the extensionless folder name here, so the path segment has
    // to carry the file's real name for the emulator to get the extension.
    const rom = romFixture({
      id: 24,
      fs_name: "B.A.T.",
      files: [
        romFileFixture({ id: 29, file_name: "B.A.T. Disk1.adf" }),
        romFileFixture({ id: 30, file_name: "B.A.T. Disk2.adf" }),
      ],
    });
    expect(getDownloadPath({ rom, fileIDs: [29] })).toBe(
      "/api/roms/24/content/B.A.T.%20Disk1.adf?file_ids=29",
    );
  });

  it("falls back to fs_name when multiple files are selected (zip)", () => {
    const rom = romFixture({
      id: 24,
      fs_name: "B.A.T.",
      files: [
        romFileFixture({ id: 29, file_name: "B.A.T. Disk1.adf" }),
        romFileFixture({ id: 30, file_name: "B.A.T. Disk2.adf" }),
      ],
    });
    expect(getDownloadPath({ rom, fileIDs: [29, 30] })).toBe(
      "/api/roms/24/content/B.A.T.?file_ids=29%2C30",
    );
  });

  it("falls back to fs_name when the selected file id is unknown", () => {
    const rom = romFixture({
      id: 24,
      fs_name: "B.A.T.",
      has_nested_single_file: false,
      files: [],
    });
    expect(getDownloadPath({ rom, fileIDs: [999] })).toBe(
      "/api/roms/24/content/B.A.T.?file_ids=999",
    );
  });

  it("marks a player's fetch after the file selection", () => {
    const rom = romFixture({
      id: 24,
      fs_name: "B.A.T.",
      files: [
        romFileFixture({ id: 29, file_name: "B.A.T. Disk1.adf" }),
        romFileFixture({ id: 30, file_name: "B.A.T. Disk2.adf" }),
      ],
    });
    expect(getDownloadPath({ rom, fileIDs: [29], purpose: "play" })).toBe(
      "/api/roms/24/content/B.A.T.%20Disk1.adf?file_ids=29&purpose=play",
    );
  });
});

describe("download URL encoding", () => {
  const rom = romFixture({
    id: 24,
    fs_name: "Game & (USA)",
    has_nested_single_file: false,
    files: [
      romFileFixture({ id: 29, file_name: "Game & (USA) Disk1.adf" }),
      romFileFixture({ id: 30, file_name: "Disk2.adf" }),
    ],
  });

  it("encodes a name that would otherwise truncate the URL", () => {
    // A bare `#` starts the fragment, so an unencoded fs_name loses
    // everything after it before the request is even sent.
    const hashRom = romFixture({ id: 7, fs_name: "Game #1 (100%)" });
    const url = new URL(getDownloadLink({ rom: hashRom }));
    expect(url.hash).toBe("");
    expect(decodeURIComponent(url.pathname)).toBe(
      "/api/roms/7/content/Game #1 (100%)",
    );
  });

  it("does not double-encode the selected file name", () => {
    const url = new URL(getDownloadLink({ rom, fileIDs: [29] }));
    expect(url.pathname).not.toContain("%25");
    expect(decodeURIComponent(url.pathname)).toBe(
      "/api/roms/24/content/Game & (USA) Disk1.adf",
    );
  });

  it("leaves file_ids parseable for a multi-file zip link", () => {
    // The backend splits this on "," and int()s each part, so a re-encoded
    // comma reaches it as one unparseable value.
    const url = new URL(getDownloadLink({ rom, fileIDs: [29, 30] }));
    expect(url.searchParams.get("file_ids")).toBe("29,30");
    expect(decodeURIComponent(url.pathname)).toBe(
      "/api/roms/24/content/Game & (USA)",
    );
  });

  it("prefixes the path with the origin and nothing else", () => {
    expect(getDownloadLink({ rom })).toBe(
      `${window.location.origin}${getDownloadPath({ rom })}`,
    );
  });
});

describe("getDownloadFileName", () => {
  it("names a flat single-file rom by its file", () => {
    const rom = romFixture({
      fs_name: "Maniac Mansion (1989).adf",
      files: [
        romFileFixture({ id: 19, file_name: "Maniac Mansion (1989).adf" }),
      ],
    });
    expect(getDownloadFileName(rom)).toBe("Maniac Mansion (1989).adf");
  });

  // The endpoint serves the sole file under its own name, so the folder's
  // name would save the payload as something the emulator cannot open.
  it("names a nested single-file rom by the file inside it", () => {
    const rom = romFixture({
      fs_name: "Art Of Fighting",
      has_nested_single_file: true,
      files: [romFileFixture({ id: 21, file_name: "aof.zip" })],
    });
    expect(getDownloadFileName(rom)).toBe("aof.zip");
  });

  // Several files come back as an archive the endpoint builds, named for the
  // rom, so the extension has to be there or nothing will open it.
  it("names a multi-file rom as the archive it is served as", () => {
    const rom = romFixture({
      fs_name: "Final Fantasy VII",
      has_multiple_files: true,
      files: [
        romFileFixture({ id: 1, file_name: "disc1.chd" }),
        romFileFixture({ id: 2, file_name: "disc2.chd" }),
      ],
    });
    expect(getDownloadFileName(rom)).toBe("Final Fantasy VII.zip");
  });

  it("falls back to the rom name when nothing is on disk", () => {
    expect(getDownloadFileName(romFixture({ fs_name: "Ghost" }))).toBe("Ghost");
  });
});

describe("getSoleRomFile", () => {
  it("returns the one file a rom resolves to", () => {
    const rom = romFixture({
      files: [
        romFileFixture({
          id: 7,
          file_name: "game.sfc",
          full_path: "snes/game.sfc",
        }),
      ],
    });
    expect(getSoleRomFile(rom)?.full_path).toBe("snes/game.sfc");
  });

  // There is no single path to a payload the endpoint assembles per request.
  it("returns nothing for a rom served as a built archive", () => {
    const rom = romFixture({
      files: [
        romFileFixture({ id: 1, file_name: "disc1.chd" }),
        romFileFixture({ id: 2, file_name: "disc2.chd" }),
      ],
    });
    expect(getSoleRomFile(rom)).toBeNull();
    expect(getSoleRomFile(romFixture({}))).toBeNull();
  });
});
describe("getDownloadPath format", () => {
  it("adds the requested format to the query", () => {
    const rom = romFixture({
      id: 3,
      fs_name: "game.chd",
      files: [romFileFixture({ id: 5, file_name: "game.chd" })],
    });
    expect(getDownloadPath({ rom, fileIDs: [5], format: "iso" })).toBe(
      "/api/roms/3/content/game.chd?file_ids=5&format=iso",
    );
  });
});
