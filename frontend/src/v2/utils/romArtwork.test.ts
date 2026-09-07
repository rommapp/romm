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
    archive_members: null,
    category: "game",
    ...overrides,
  };
}

function makeRom(
  files: RomFileSchema[],
  overrides: Partial<DetailedRom> = {},
): DetailedRom {
  return {
    updated_at: "2024-01-01T00:00:00Z",
    ss_metadata: null,
    gamelist_metadata: null,
    path_video: null,
    files,
    ...overrides,
  } as DetailedRom;
}

describe("resolveRomArtwork — cover", () => {
  it("leads with the rom's own cover, already a browser-ready URL", () => {
    const rom = makeRom([], {
      path_cover_large: "/assets/romm/resources/roms/1/1/cover/big.png?ts=x",
      ss_metadata: { logo_path: "roms/1/1/logo/logo.png" },
    });
    const entries = resolveRomArtwork(rom);

    expect(entries.map((e) => e.key)).toEqual(["cover", "logo"]);
    expect(entries[0].url).toBe(
      "/assets/romm/resources/roms/1/1/cover/big.png?ts=x",
    );
  });

  it("falls back to the provider cover when nothing was stored locally", () => {
    const rom = makeRom([], {
      path_cover_large: "",
      path_cover_small: "",
      url_cover: "https://provider.example/cover.png",
    });

    expect(resolveRomArtwork(rom)[0].url).toBe(
      "https://provider.example/cover.png",
    );
  });

  it("omits the cover when the rom has none", () => {
    const rom = makeRom([], { path_cover_large: "", path_cover_small: "" });

    expect(resolveRomArtwork(rom)).toHaveLength(0);
  });
});

describe("resolveRomArtwork — scraped resources", () => {
  it("includes the ScreenScraper box front, which no other surface shows", () => {
    const rom = makeRom([], {
      ss_metadata: {
        box2d_path: "roms/1/1/box2d/box2d.png",
        box2d_back_path: "roms/1/1/box2d_back/box2d_back.png",
      },
    });
    const entries = resolveRomArtwork(rom);

    expect(entries.map((e) => e.key)).toEqual(["box2d", "box2d_back"]);
    expect(entries[0].url).toContain("roms/1/1/box2d/box2d.png");
  });

  it("omits the box front when it was not stored locally", () => {
    const rom = makeRom([], {
      ss_metadata: { box2d_url: "https://screenscraper.example.com/box-2D" },
    });

    expect(resolveRomArtwork(rom)).toHaveLength(0);
  });
});

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

  it("ignores media nested inside the game's own data", () => {
    const rom = makeRom([
      makeFile({
        id: 1,
        file_name: "Demo101_0.mp4",
        file_path: "platform/roms/game/content/Movie",
        full_path: "platform/roms/game/content/Movie/Demo101_0.mp4",
        is_top_level: false,
        category: null,
      }),
      makeFile({ id: 2, file_name: "trailer.mp4" }),
    ]);
    const entries = resolveRomArtwork(rom);

    expect(entries).toHaveLength(1);
    expect(entries[0].label).toBe("trailer");
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
