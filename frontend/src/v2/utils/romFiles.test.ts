import { describe, expect, it } from "vitest";
import type { RomFileSchema } from "@/__generated__";
import { FRONTEND_RESOURCES_PATH } from "@/utils";
import {
  romFileUrl,
  versionedResourceUrl,
  versionedRomFileUrl,
} from "./romFiles";

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
  title_id: null,
  title_version: null,
  title: null,
  serial: null,
  content_type: null,
  display_version: null,
  regions: null,
  languages: null,
  publisher: null,
  min_firmware_version: null,
  is_compressed: null,
  compression: null,
  file_format: null,
  uncompressed_size_bytes: null,
  icon_path: null,
  banner_path: null,
  background_path: null,
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

describe("versionedResourceUrl", () => {
  it("serves the path from the resources root, versioned by the ROM timestamp", () => {
    expect(
      versionedResourceUrl("roms/1/2/logo/logo.png", "2024-02-03T04:05:06"),
    ).toBe(
      `${FRONTEND_RESOURCES_PATH}/roms/1/2/logo/logo.png?v=2024-02-03T04%3A05%3A06`,
    );
  });
});
