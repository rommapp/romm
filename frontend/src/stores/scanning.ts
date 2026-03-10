import { defineStore } from "pinia";
import type { ScanStats } from "@/__generated__";
import type { SimpleRom } from "@/stores/roms";
import type { Platform } from "./platforms";

export interface ScanningPlatform extends Pick<
  Platform,
  | "id"
  | "name"
  | "display_name"
  | "slug"
  | "fs_slug"
  | "is_identified"
  | "firmware_count"
> {
  roms: SimpleRom[];
}

export default defineStore("scanning", {
  state: () => ({
    scanning: false,
    scanningPlatforms: [] as ScanningPlatform[],
    scanStats: {} as ScanStats,
  }),

  actions: {
    setScanning(scanning: boolean) {
      this.scanning = scanning;
    },
    setScanStats(stats: ScanStats) {
      this.scanStats = stats;
    },
    reset() {
      this.scanning = false;
      this.scanningPlatforms = [] as ScanningPlatform[];
      this.scanStats = {
        total_platforms: 0,
        scanned_platforms: 0,
        new_platforms: 0,
        identified_platforms: 0,
        total_roms: 0,
        scanned_roms: 0,
        new_roms: 0,
        identified_roms: 0,
        scanned_firmware: 0,
        new_firmware: 0,
      };
    },
  },
});
