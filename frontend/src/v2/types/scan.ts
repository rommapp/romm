// Mirrors `ScanType` in backend/handler/scan_handler.py: scans start over
// Socket.IO, so the enum never reaches the OpenAPI schema.
export type ScanType =
  | "new_platforms"
  | "quick"
  | "unmatched"
  | "update"
  | "hashes"
  | "title_ids"
  | "complete";

/** Whether a scan type is worth starting with no metadata source picked. A
 *  quick scan reconciles files on its own, and a title-ids scan reads the
 *  binaries, so neither has anything to ask a provider. */
export function scanNeedsMetadataSource(scanType: ScanType): boolean {
  return scanType !== "quick" && scanType !== "title_ids";
}

/** One `scan` socket event. The provider flags are optional because a
 *  per-rom file refresh sends none of them. */
export interface ScanRequest {
  type: ScanType;
  platforms?: number[];
  platform_fs_slugs?: string[];
  roms_ids?: number[];
  apis: string[];
  launchbox_remote_enabled?: boolean;
}
