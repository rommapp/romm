// Mirrors `ScanType` in backend/handler/scan_handler.py: scans start over
// Socket.IO, so the enum never reaches the OpenAPI schema.
export type ScanType =
  | "new_platforms"
  | "quick"
  | "files"
  | "unmatched"
  | "update"
  | "hashes"
  | "complete";

/** One `scan` socket event. The provider flags are optional because a files
 *  scan sends none of them. */
export interface ScanRequest {
  type: ScanType;
  platforms?: number[];
  platform_fs_slugs?: string[];
  roms_ids?: number[];
  apis: string[];
  launchbox_remote_enabled?: boolean;
  playmatch_enabled?: boolean;
}
