// Scan types accepted by the `scan` socket event. Mirrors `ScanType` in
// backend/handler/scan_handler.py, which never reaches the OpenAPI schema
// because scans are started over Socket.IO rather than REST.
export type ScanType =
  | "new_platforms"
  | "quick"
  | "files"
  | "unmatched"
  | "update"
  | "hashes"
  | "complete";

export interface ScanPayload {
  type: ScanType;
  platforms?: number[];
  platform_fs_slugs?: string[];
  roms_ids?: number[];
  apis: string[];
  launchbox_remote_enabled?: boolean;
  playmatch_enabled?: boolean;
}
