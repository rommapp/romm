import { describe, expect, it } from "vitest";
import type {
  RomFileSchema,
  RomUserSchema,
  UserScreenshotSchema,
} from "@/__generated__";
import type { DetailedRom } from "@/stores/roms";
import {
  defaultPinnedMediaKeys,
  resolvePinnedMedia,
  romFolderScreenshots,
  togglePinnedMediaKey,
} from "./pinnedMedia";

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
    category: null,
    ...overrides,
  };
}

const folderShot = makeFile({
  id: 5,
  file_name: "shot.png",
  file_path: "platform/roms/game/screenshots",
  full_path: "platform/roms/game/screenshots/shot.png",
  is_top_level: false,
  category: "screenshot",
});
const trailer = makeFile({ id: 6, file_name: "trailer.mp4" });
const fanart = makeFile({ id: 7, file_name: "fanart.png" });

function makeRom(
  pinnedMedia: string[] | null,
  overrides: Partial<DetailedRom> = {},
): DetailedRom {
  return {
    id: 1,
    updated_at: "2024-01-01T00:00:00Z",
    full_path: "platform/roms/game",
    ss_metadata: null,
    gamelist_metadata: null,
    merged_screenshots: ["/assets/romm/resources/roms/1/1/screenshots/0.jpg"],
    files: [folderShot, trailer, fanart],
    all_user_screenshots: [
      { id: 9, download_path: "/api/screenshots/9/content/mine.png" },
    ] as UserScreenshotSchema[],
    rom_user: { pinned_media: pinnedMedia } as RomUserSchema,
    ...overrides,
  } as DetailedRom;
}

describe("romFolderScreenshots", () => {
  it("keeps only images under the screenshots folder", () => {
    const notes = makeFile({
      id: 8,
      file_name: "notes.txt",
      full_path: "platform/roms/game/screenshots/notes.txt",
    });
    const rom = makeRom(null, { files: [folderShot, fanart, notes] });

    expect(romFolderScreenshots(rom)).toEqual([folderShot]);
  });
});

describe("defaultPinnedMediaKeys", () => {
  it("selects scraped and folder screenshots, then videos", () => {
    expect(defaultPinnedMediaKeys(makeRom(null))).toEqual([
      "scraped:/assets/romm/resources/roms/1/1/screenshots/0.jpg",
      "file:5",
      "file:6",
    ]);
  });
});

describe("resolvePinnedMedia", () => {
  it("falls back to the default selection until the user pins anything", () => {
    const items = resolvePinnedMedia(makeRom(null));

    expect(items.map((item) => item.key)).toEqual(
      defaultPinnedMediaKeys(makeRom(null)),
    );
    expect(items[2].isVideo).toBe(true);
  });

  it("follows the pinned order across every media source", () => {
    const rom = makeRom(["screenshot:9", "file:7", "artwork:cover"], {
      path_cover_large: "/assets/romm/resources/roms/1/1/cover/big.png",
    });

    expect(resolvePinnedMedia(rom).map((item) => item.url)).toEqual([
      "/api/screenshots/9/content/mine.png",
      expect.stringContaining("/api/roms/7/files/content/fanart.png"),
      "/assets/romm/resources/roms/1/1/cover/big.png",
    ]);
  });

  it("skips keys whose media is gone", () => {
    const rom = makeRom(["file:404", "screenshot:9"]);

    expect(resolvePinnedMedia(rom).map((item) => item.key)).toEqual([
      "screenshot:9",
    ]);
  });

  it("shows nothing once everything is unpinned", () => {
    expect(resolvePinnedMedia(makeRom([]))).toEqual([]);
  });
});

describe("togglePinnedMediaKey", () => {
  it("appends a new key and removes a pinned one", () => {
    expect(togglePinnedMediaKey(["file:1"], "file:2")).toEqual([
      "file:1",
      "file:2",
    ]);
    expect(togglePinnedMediaKey(["file:1", "file:2"], "file:1")).toEqual([
      "file:2",
    ]);
  });
});
