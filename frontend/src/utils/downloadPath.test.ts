import { describe, expect, it } from "vitest";
import type { SimpleRom } from "@/stores/roms";
import {
  getDownloadFileName,
  getDownloadLink,
  getDownloadPath,
  getSoleRomFile,
} from "./downloadPath";
import { makeRom } from "./rom.fixtures";

describe("getDownloadPath", () => {
  it("uses fs_name for a flat single-file rom", () => {
    const rom = makeRom({
      id: 14,
      fs_name: "Maniac Mansion (1989).adf",
      has_nested_single_file: false,
      files: [
        { id: 19, file_name: "Maniac Mansion (1989).adf" },
      ] as SimpleRom["files"],
    });
    expect(getDownloadPath({ rom })).toBe(
      "/api/roms/14/content/Maniac%20Mansion%20(1989).adf",
    );
  });

  it("uses the file name for a nested single-file rom", () => {
    const rom = makeRom({
      id: 21,
      fs_name: "Art Of Fighting",
      has_nested_single_file: true,
      files: [{ id: 26, file_name: "aof.zip" }] as SimpleRom["files"],
    });
    expect(getDownloadPath({ rom })).toBe("/api/roms/21/content/aof.zip");
  });

  it("uses fs_name for an unselected multi-file rom", () => {
    const rom = makeRom({
      id: 24,
      fs_name: "B.A.T.",
      has_nested_single_file: false,
      files: [
        { id: 29, file_name: "B.A.T. Disk1.adf" },
        { id: 30, file_name: "B.A.T. Disk2.adf" },
      ] as SimpleRom["files"],
    });
    expect(getDownloadPath({ rom })).toBe("/api/roms/24/content/B.A.T.");
  });

  it("uses the selected file name (with extension) for a single file", () => {
    // fs_name is the extensionless folder name here, so the path segment has
    // to carry the file's real name for the emulator to get the extension.
    const rom = makeRom({
      id: 24,
      fs_name: "B.A.T.",
      files: [
        { id: 29, file_name: "B.A.T. Disk1.adf" },
        { id: 30, file_name: "B.A.T. Disk2.adf" },
      ] as SimpleRom["files"],
    });
    expect(getDownloadPath({ rom, fileIDs: [29] })).toBe(
      "/api/roms/24/content/B.A.T.%20Disk1.adf?file_ids=29",
    );
  });

  it("falls back to fs_name when multiple files are selected (zip)", () => {
    const rom = makeRom({
      id: 24,
      fs_name: "B.A.T.",
      files: [
        { id: 29, file_name: "B.A.T. Disk1.adf" },
        { id: 30, file_name: "B.A.T. Disk2.adf" },
      ] as SimpleRom["files"],
    });
    expect(getDownloadPath({ rom, fileIDs: [29, 30] })).toBe(
      "/api/roms/24/content/B.A.T.?file_ids=29%2C30",
    );
  });

  it("falls back to fs_name when the selected file id is unknown", () => {
    const rom = makeRom({
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
    const rom = makeRom({
      id: 24,
      fs_name: "B.A.T.",
      files: [
        { id: 29, file_name: "B.A.T. Disk1.adf" },
        { id: 30, file_name: "B.A.T. Disk2.adf" },
      ] as SimpleRom["files"],
    });
    expect(getDownloadPath({ rom, fileIDs: [29], purpose: "play" })).toBe(
      "/api/roms/24/content/B.A.T.%20Disk1.adf?file_ids=29&purpose=play",
    );
  });
});

describe("download URL encoding", () => {
  const rom = makeRom({
    id: 24,
    fs_name: "Game & (USA)",
    has_nested_single_file: false,
    files: [
      { id: 29, file_name: "Game & (USA) Disk1.adf" },
      { id: 30, file_name: "Disk2.adf" },
    ] as SimpleRom["files"],
  });

  it("encodes a name that would otherwise truncate the URL", () => {
    // A bare `#` starts the fragment, so an unencoded fs_name loses
    // everything after it before the request is even sent.
    const hashRom = makeRom({ id: 7, fs_name: "Game #1 (100%)" });
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
    const rom = makeRom({
      fs_name: "Maniac Mansion (1989).adf",
      files: [
        { id: 19, file_name: "Maniac Mansion (1989).adf" },
      ] as SimpleRom["files"],
    });
    expect(getDownloadFileName(rom)).toBe("Maniac Mansion (1989).adf");
  });

  // The endpoint serves the sole file under its own name, so the folder's
  // name would save the payload as something the emulator cannot open.
  it("names a nested single-file rom by the file inside it", () => {
    const rom = makeRom({
      fs_name: "Art Of Fighting",
      has_nested_single_file: true,
      files: [{ id: 21, file_name: "aof.zip" }] as SimpleRom["files"],
    });
    expect(getDownloadFileName(rom)).toBe("aof.zip");
  });

  // Several files come back as an archive the endpoint builds, named for the
  // rom, so the extension has to be there or nothing will open it.
  it("names a multi-file rom as the archive it is served as", () => {
    const rom = makeRom({
      fs_name: "Final Fantasy VII",
      has_multiple_files: true,
      files: [
        { id: 1, file_name: "disc1.chd" },
        { id: 2, file_name: "disc2.chd" },
      ] as SimpleRom["files"],
    });
    expect(getDownloadFileName(rom)).toBe("Final Fantasy VII.zip");
  });

  it("falls back to the rom name when nothing is on disk", () => {
    expect(getDownloadFileName(makeRom({ fs_name: "Ghost" }))).toBe("Ghost");
  });
});

describe("getSoleRomFile", () => {
  it("returns the one file a rom resolves to", () => {
    const rom = makeRom({
      files: [
        { id: 7, file_name: "game.sfc", full_path: "snes/game.sfc" },
      ] as SimpleRom["files"],
    });
    expect(getSoleRomFile(rom)?.full_path).toBe("snes/game.sfc");
  });

  // There is no single path to a payload the endpoint assembles per request.
  it("returns nothing for a rom served as a built archive", () => {
    const rom = makeRom({
      files: [
        { id: 1, file_name: "disc1.chd" },
        { id: 2, file_name: "disc2.chd" },
      ] as SimpleRom["files"],
    });
    expect(getSoleRomFile(rom)).toBeNull();
    expect(getSoleRomFile(makeRom({}))).toBeNull();
  });
});
