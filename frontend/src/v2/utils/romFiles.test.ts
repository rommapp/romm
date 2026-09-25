import { describe, expect, it } from "vitest";
import type { RomFileSchema } from "@/__generated__";
import type { DetailedRom } from "@/stores/roms";
import { hasDiscImage, romFileUrl, versionedRomFileUrl } from "./romFiles";

const file: RomFileSchema = {
  id: 7,
  rom_id: 1,
  file_name: "title screen #1.png",
  file_path: "platform/roms/game/screenshots",
  file_size_bytes: 10,
  full_path: "platform/roms/game/screenshots/title screen #1.png",
  is_top_level: false,
  created_at: "2024-01-01T00:00:00Z",
  updated_at: "2024-02-03T04:05:06+00:00",
  last_modified: "2024-01-01T00:00:00Z",
  crc_hash: null,
  md5_hash: null,
  sha1_hash: null,
  ra_hash: null,
  chd_sha1_hash: null,
  archive_members: null,
  category: "screenshot",
};

describe("romFileUrl", () => {
  it("encodes the file name into the content endpoint", () => {
    expect(romFileUrl(7, "title screen #1.png")).toBe(
      "/api/roms/7/files/content/title%20screen%20%231.png",
    );
  });
});

describe("versionedRomFileUrl", () => {
  it("versions the URL with the file's own timestamp", () => {
    expect(versionedRomFileUrl(file)).toBe(
      "/api/roms/7/files/content/title%20screen%20%231.png?v=2024-02-03T04%3A05%3A06%2B00%3A00",
    );
  });

  it("changes when the file row is updated", () => {
    const replaced = { ...file, updated_at: "2024-03-01T00:00:00+00:00" };
    expect(versionedRomFileUrl(replaced)).not.toBe(versionedRomFileUrl(file));
  });
});

describe("hasDiscImage", () => {
  function disc(
    files: Partial<RomFileSchema>[],
    hasSimpleSingleFile = false,
  ): DetailedRom {
    return {
      has_simple_single_file: hasSimpleSingleFile,
      files: files.map((overrides) => ({ ...file, ...overrides })),
    } as DetailedRom;
  }

  it("finds a game cue sheet in a disc folder", () => {
    expect(
      hasDiscImage(
        disc([
          { file_name: "Game.CUE", category: "game" },
          { file_name: "Game (Track 1).bin", category: "game" },
        ]),
      ),
    ).toBe(true);
    expect(
      hasDiscImage(disc([{ file_name: "Game.cue", category: null }])),
    ).toBe(true);
  });

  it("finds a CHD, even alone in the platform folder", () => {
    expect(
      hasDiscImage(disc([{ file_name: "Game.chd", category: "game" }], true)),
    ).toBe(true);
  });

  it("ignores cue sheets outside the game files", () => {
    expect(
      hasDiscImage(disc([{ file_name: "Game.cue", category: "soundtrack" }])),
    ).toBe(false);
  });

  it("refuses a sheet loose in the platform folder", () => {
    expect(
      hasDiscImage(disc([{ file_name: "Game.cue", category: "game" }], true)),
    ).toBe(false);
  });
});
