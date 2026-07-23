import { describe, expect, it } from "vitest";
import type { RomFileSchema } from "@/__generated__";
import type { DetailedRom } from "@/stores/roms";
import { resolveRomArtwork } from "./romArtwork";

function makeFile(overrides: Partial<RomFileSchema>): RomFileSchema {
  return {
    id: 1,
    rom_id: 1,
    file_name: "file.bin",
    file_path: "platform/roms/game",
    file_size_bytes: 10,
    full_path: "platform/roms/game/file.bin",
    is_top_level: true,
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-01-01T00:00:00Z",
    last_modified: "2024-01-01T00:00:00Z",
    crc_hash: null,
    md5_hash: null,
    sha1_hash: null,
    ra_hash: null,
    chd_sha1_hash: null,
    title_id: null,
    save_id: null,
    archive_members: null,
    category: "game",
    ...overrides,
  };
}

function makeRom(files: RomFileSchema[]): DetailedRom {
  return {
    updated_at: "2024-01-01T00:00:00Z",
    ss_metadata: null,
    gamelist_metadata: null,
    path_video: null,
    files,
  } as DetailedRom;
}

describe("resolveRomArtwork — library media files", () => {
  it("includes image files as non-video entries pointing at the content endpoint", () => {
    const rom = makeRom([makeFile({ id: 7, file_name: "artwork.png" })]);
    const entries = resolveRomArtwork(rom);

    expect(entries).toHaveLength(1);
    expect(entries[0].isVideo).toBe(false);
    expect(entries[0].label).toBe("artwork");
    expect(entries[0].url).toContain("/api/roms/7/files/content/artwork.png");
  });

  it("includes video files as video entries", () => {
    const rom = makeRom([makeFile({ id: 3, file_name: "trailer.mp4" })]);
    const entries = resolveRomArtwork(rom);

    expect(entries).toHaveLength(1);
    expect(entries[0].isVideo).toBe(true);
    expect(entries[0].label).toBe("trailer");
  });

  it("ignores files that are not a known media type", () => {
    const rom = makeRom([
      makeFile({ id: 1, file_name: "game.bin" }),
      makeFile({ id: 2, file_name: "notes.txt" }),
    ]);
    expect(resolveRomArtwork(rom)).toHaveLength(0);
  });

  it("skips categories that have their own surface", () => {
    const rom = makeRom([
      makeFile({ id: 1, file_name: "shot.png", category: "screenshot" }),
      makeFile({ id: 2, file_name: "track.mp4", category: "soundtrack" }),
      makeFile({ id: 3, file_name: "book.png", category: "manual" }),
      makeFile({ id: 4, file_name: "keep.png", category: "game" }),
    ]);
    const entries = resolveRomArtwork(rom);

    expect(entries).toHaveLength(1);
    expect(entries[0].label).toBe("keep");
  });

  it("orders image files before video files", () => {
    const rom = makeRom([
      makeFile({ id: 1, file_name: "clip.mp4" }),
      makeFile({ id: 2, file_name: "pic.jpg" }),
    ]);
    const entries = resolveRomArtwork(rom);

    expect(entries.map((e) => e.isVideo)).toEqual([false, true]);
  });
});
