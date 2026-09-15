import { describe, expect, it } from "vitest";
import type { RomFileSchema, UserScreenshotSchema } from "@/__generated__";
import type { DetailedRom } from "@/stores/roms";
import { overviewScreenshotUrls } from "@/v2/utils/romScreenshots";

function rom(overrides: Partial<DetailedRom> = {}): DetailedRom {
  return {
    id: 1,
    updated_at: "2026-09-15T10:00:00Z",
    merged_screenshots: ["/metadata.png"],
    files: [],
    all_user_screenshots: [],
    ...overrides,
  } as DetailedRom;
}

function romFile(overrides: Partial<RomFileSchema>): RomFileSchema {
  return {
    id: 1,
    rom_id: 1,
    file_name: "screenshot.png",
    file_path: "roms/game/screenshots",
    file_size_bytes: 100,
    full_path: "roms/game/screenshots/screenshot.png",
    is_top_level: false,
    created_at: "2026-09-15T10:00:00Z",
    updated_at: "2026-09-15T10:00:00Z",
    last_modified: "2026-09-15T10:00:00Z",
    crc_hash: null,
    md5_hash: null,
    sha1_hash: null,
    ra_hash: null,
    chd_sha1_hash: null,
    archive_members: null,
    category: "screenshot",
    ...overrides,
  };
}

function userScreenshot(
  overrides: Partial<UserScreenshotSchema>,
): UserScreenshotSchema {
  return {
    id: 10,
    rom_id: 1,
    user_id: 1,
    file_name: "personal.png",
    file_name_no_tags: "personal",
    file_name_no_ext: "personal",
    file_extension: "png",
    file_path: "screenshots/1",
    file_size_bytes: 100,
    full_path: "screenshots/1/personal.png",
    download_path: "/api/screenshots/10/content/personal.png",
    missing_from_fs: false,
    created_at: "2026-09-15T10:00:00Z",
    updated_at: "2026-09-15T10:00:00Z",
    is_gallery: true,
    is_public: true,
    is_overview: true,
    username: "owner",
    ...overrides,
  };
}

describe("overviewScreenshotUrls", () => {
  it("combines metadata, general, and public selected user screenshots", () => {
    const result = overviewScreenshotUrls(
      rom({
        files: [
          romFile({
            id: 4,
            file_name: "shared shot.png",
          }),
          romFile({
            id: 5,
            file_name: "general.png",
          }),
        ],
        all_user_screenshots: [
          userScreenshot({}),
          userScreenshot({ id: 11, is_overview: false }),
          userScreenshot({ id: 12, is_public: false, is_overview: true }),
        ],
      }),
    );

    expect(result).toEqual([
      "/metadata.png",
      "/api/roms/4/files/content/shared%20shot.png?v=2026-09-15T10%3A00%3A00Z",
      "/api/roms/5/files/content/general.png?v=2026-09-15T10%3A00%3A00Z",
      "/api/screenshots/10/content/personal.png",
    ]);
  });
});
