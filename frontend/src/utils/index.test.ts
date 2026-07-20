import { describe, expect, it } from "vitest";
import type { SimpleRom } from "@/stores/roms";
import { getDownloadPath } from "./index";

function makeRom(overrides: Partial<SimpleRom>): SimpleRom {
  return {
    id: 1,
    fs_name: "Game",
    files: [],
    ...overrides,
  } as SimpleRom;
}

describe("getDownloadPath", () => {
  it("uses fs_name when no file is selected", () => {
    const rom = makeRom({ id: 14, fs_name: "Maniac Mansion (1989).adf" });
    expect(getDownloadPath({ rom })).toBe(
      "/api/roms/14/content/Maniac Mansion (1989).adf",
    );
  });

  it("uses the selected file name (with extension) for a single file", () => {
    // Multi-file rom: fs_name is the folder name with no extension. The URL
    // path segment must carry the selected file's real name so the emulator
    // receives a file with the correct extension.
    const rom = makeRom({
      id: 24,
      fs_name: "B.A.T.",
      files: [
        { id: 29, file_name: "B.A.T. Disk1.adf" },
        { id: 30, file_name: "B.A.T. Disk2.adf" },
      ] as SimpleRom["files"],
    });
    expect(getDownloadPath({ rom, fileIDs: [29] })).toBe(
      "/api/roms/24/content/B.A.T. Disk1.adf?file_ids=29",
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
    const rom = makeRom({ id: 24, fs_name: "B.A.T." });
    expect(getDownloadPath({ rom, fileIDs: [999] })).toBe(
      "/api/roms/24/content/B.A.T.?file_ids=999",
    );
  });
});
