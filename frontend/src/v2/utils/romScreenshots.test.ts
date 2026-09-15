import { describe, expect, it } from "vitest";
import type { RomFileSchema } from "@/__generated__";
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

describe("overviewScreenshotUrls", () => {
  it("combines metadata and selected uploaded screenshots", () => {
    const result = overviewScreenshotUrls(
      rom({
        files: [
          romFile({
            id: 4,
            file_name: "shared shot.png",
            is_on_overview: true,
          }),
          romFile({
            id: 5,
            file_name: "hidden.png",
            is_on_overview: false,
          }),
        ],
      }),
    );

    expect(result).toEqual([
      "/metadata.png",
      "/api/roms/4/files/content/shared%20shot.png?v=2026-09-15T10%3A00%3A00Z",
    ]);
  });
});
