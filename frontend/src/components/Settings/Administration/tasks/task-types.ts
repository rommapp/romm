// Shared types for task components
export interface ScanStats {
  total_platforms: number;
  total_roms: number;
  scanned_platforms: number;
  new_platforms: number;
  identified_platforms: number;
  scanned_roms: number;
  added_roms: number;
  metadata_roms: number;
  scanned_firmware: number;
  added_firmware: number;
}

export interface ConversionStats {
  processed: number;
  errors: number;
  total: number;
  errorList: string[];
}

export interface CleanupStats {
  removed: number;
}

export interface DownloadProgress {
  progress: number;
  total: number;
  current: number;
}

export interface TaskProgress {
  platforms?: string;
  roms?: string;
  addedRoms?: number;
  metadataRoms?: number;
  scannedFirmware?: number;
  addedFirmware?: number;
  processed?: string;
  errors?: number;
  successRate?: number;
  removed?: number;
  downloaded?: string;
}

export interface ProgressPercentages {
  platforms?: number;
  roms?: number;
  conversion?: number;
  download?: number;
}

export type TaskType =
  | "scan"
  | "conversion"
  | "cleanup"
  | "update"
  | "watcher"
  | "generic";
