import type { FirmwareSchema } from "@/__generated__";

export function firmwareFixture(
  overrides: Partial<FirmwareSchema> = {},
): FirmwareSchema {
  return {
    id: 1,
    platform_id: 1,
    file_name: "bios.bin",
    file_name_no_tags: "bios",
    file_name_no_ext: "bios",
    file_extension: "bin",
    file_path: "psx/bios",
    file_size_bytes: 524288,
    full_path: "psx/bios/bios.bin",
    is_verified: false,
    crc_hash: "",
    md5_hash: "",
    sha1_hash: "",
    missing_from_fs: false,
    created_at: "2026-09-16T12:00:00Z",
    updated_at: "2026-09-16T12:00:00Z",
    ...overrides,
  };
}
