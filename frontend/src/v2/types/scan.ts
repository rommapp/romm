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

/** Scan types that read the library on their own and contact no provider. */
const SELF_CONTAINED_SCANS: ReadonlySet<ScanType> = new Set<ScanType>([
  "quick",
  "title_ids",
]);

/** Whether a scan type is worth starting with no metadata source picked. */
export function scanNeedsMetadataSource(scanType: ScanType): boolean {
  return !SELF_CONTAINED_SCANS.has(scanType);
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
