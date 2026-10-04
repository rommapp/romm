import { describe, expect, it } from "vitest";
import type { RomFileSchema } from "@/__generated__";
import type { DetailedRom } from "@/stores/roms";
import { detailedRomFixture, romFileFixture } from "@/utils/rom.fixtures";
import { resolveRomArtwork } from "./romArtwork";

function makeFile(overrides: Partial<RomFileSchema>): RomFileSchema {
  return romFileFixture({
    file_name: "file.bin",
    file_path: "platform/roms/game",
    file_size_bytes: 10,
    full_path: "platform/roms/game/file.bin",
    is_top_level: true,
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-01-01T00:00:00Z",
    last_modified: "2024-01-01T00:00:00Z",
    category: "game",
    ...overrides,
  });
}

function romWithFiles(
  files: RomFileSchema[],
  overrides: Partial<DetailedRom> = {},
): DetailedRom {
  return detailedRomFixture({
    updated_at: "2024-01-01T00:00:00Z",
    files,
    ...overrides,
  });
}

describe("resolveRomArtwork — cover", () => {
  it("leads with the rom's own cover, already a browser-ready URL", () => {
    const rom = romWithFiles([], {
      path_cover_large: "/assets/romm/resources/roms/1/1/cover/big.png?ts=x",
      ss_metadata: { logo_path: "roms/1/1/logo/logo.png" },
    });
    const entries = resolveRomArtwork(rom);

    expect(entries.map((e) => e.key)).toEqual([
      "artwork:cover",
      "artwork:logo",
    ]);
    expect(entries[0]?.url).toBe(
      "/assets/romm/resources/roms/1/1/cover/big.png?ts=x",
    );
  });

  it("falls back to the provider cover when nothing was stored locally", () => {
    const rom = romWithFiles([], {
      path_cover_large: "",
      path_cover_small: "",
      url_cover: "https://provider.example/cover.png",
    });

    expect(resolveRomArtwork(rom)[0]?.url).toBe(
      "https://provider.example/cover.png",
    );
  });

  it("omits the cover when the rom has none", () => {
    const rom = romWithFiles([], {
      path_cover_large: "",
      path_cover_small: "",
    });

    expect(resolveRomArtwork(rom)).toHaveLength(0);
  });
});

describe("resolveRomArtwork — scraped resources", () => {
  it("includes the ScreenScraper box front, which no other surface shows", () => {
    const rom = romWithFiles([], {
      ss_metadata: {
        box2d_path: "roms/1/1/box2d/box2d.png",
        box2d_back_path: "roms/1/1/box2d_back/box2d_back.png",
      },
    });
    const entries = resolveRomArtwork(rom);

    expect(entries.map((e) => e.key)).toEqual([
      "artwork:box2d",
      "artwork:box2d_back",
    ]);
    expect(entries[0]?.url).toContain("roms/1/1/box2d/box2d.png");
  });

  it("fills box art ScreenScraper lacks from LaunchBox", () => {
    const rom = romWithFiles([], {
      ss_metadata: { box2d_path: "roms/1/1/box2d/ss.png" },
      launchbox_metadata: {
        box2d_path: "roms/1/1/box2d/lb.png",
        box2d_back_path: "roms/1/1/box2d_back/box2d_back.png",
        box2d_side_path: "roms/1/1/box2d_side/box2d_side.png",
        box3d_path: "roms/1/1/box3d/box3d.png",
      },
    });
    const entries = resolveRomArtwork(rom);

    expect(entries.map((e) => e.key)).toEqual([
      "artwork:box3d",
      "artwork:box2d",
      "artwork:box2d_back",
      "artwork:box2d_side",
    ]);
    expect(entries[1]?.url).toContain("roms/1/1/box2d/ss.png");
  });

  it("omits the box front when it was not stored locally", () => {
    const rom = romWithFiles([], {
      ss_metadata: { box2d_url: "https://screenscraper.example.com/box-2D" },
    });

    expect(resolveRomArtwork(rom)).toHaveLength(0);
  });

  it("lists the art of every disc of a multi-disc game", () => {
    const rom = romWithFiles([], {
      ss_metadata: {
        physical_path: "roms/1/1/physical/physical.png",
        physical_disc: 1,
        physical_extra_discs: [
          {
            disc: 2,
            url: "https://screenscraper.example.com/support-2D[2]",
            path: "roms/1/1/physical/physical_disc2.png",
          },
          {
            disc: 3,
            url: "https://screenscraper.example.com/support-2D[3]",
            path: null,
          },
        ],
      },
    });
    const entries = resolveRomArtwork(rom);

    expect(entries.map((e) => e.key)).toEqual([
      "artwork:physical",
      "artwork:physical_disc2",
    ]);
    expect(entries.map((e) => e.label)).toEqual([
      "Physical media (disc 1)",
      "Physical media (disc 2)",
    ]);
    expect(entries[1]?.url).toContain("roms/1/1/physical/physical_disc2.png");
  });

  it("keeps the plain label when no other disc has art on disk", () => {
    const rom = romWithFiles([], {
      ss_metadata: {
        physical_path: "roms/1/1/physical/physical.png",
        physical_disc: 1,
        physical_extra_discs: [
          {
            disc: 2,
            url: "https://screenscraper.example.com/support-2D[2]",
            path: null,
          },
        ],
      },
    });

    expect(resolveRomArtwork(rom).map((e) => e.label)).toEqual([
      "Physical media",
    ]);
  });
});

describe("resolveRomArtwork — library media files", () => {
  it("includes image files as non-video entries pointing at the content endpoint", () => {
    const rom = romWithFiles([makeFile({ id: 7, file_name: "artwork.png" })]);
    const entries = resolveRomArtwork(rom);

    expect(entries).toHaveLength(1);
    expect(entries[0]?.isVideo).toBe(false);
    expect(entries[0]?.label).toBe("artwork");
    expect(entries[0]?.url).toContain("/api/roms/7/files/content/artwork.png");
  });

  it("includes video files as video entries", () => {
    const rom = romWithFiles([makeFile({ id: 3, file_name: "trailer.mp4" })]);
    const entries = resolveRomArtwork(rom);

    expect(entries).toHaveLength(1);
    expect(entries[0]?.isVideo).toBe(true);
    expect(entries[0]?.label).toBe("trailer");
  });

  it("ignores files that are not a known media type", () => {
    const rom = romWithFiles([
      makeFile({ id: 1, file_name: "game.bin" }),
      makeFile({ id: 2, file_name: "notes.txt" }),
    ]);
    expect(resolveRomArtwork(rom)).toHaveLength(0);
  });

  it("skips categories that have their own surface", () => {
    const rom = romWithFiles([
      makeFile({ id: 1, file_name: "shot.png", category: "screenshot" }),
      makeFile({ id: 2, file_name: "track.mp4", category: "soundtrack" }),
      makeFile({ id: 3, file_name: "book.png", category: "manual" }),
      makeFile({ id: 4, file_name: "keep.png", category: "game" }),
    ]);
    const entries = resolveRomArtwork(rom);

    expect(entries).toHaveLength(1);
    expect(entries[0]?.label).toBe("keep");
  });

  it("ignores media nested inside the game's own data", () => {
    const rom = romWithFiles([
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
    expect(entries[0]?.label).toBe("trailer");
  });

  it("orders image files before video files", () => {
    const rom = romWithFiles([
      makeFile({ id: 1, file_name: "clip.mp4" }),
      makeFile({ id: 2, file_name: "pic.jpg" }),
    ]);
    const entries = resolveRomArtwork(rom);

    expect(entries.map((e) => e.isVideo)).toEqual([false, true]);
  });
});
