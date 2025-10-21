import { defineStore } from "pinia";
import type { SimpleRom } from "@/stores/roms";
import type { Platform } from "./platforms";

interface ScanningPlatform extends Partial<Platform> {
  roms: SimpleRom[];
}

export default defineStore("scanning", {
  state: () => ({
    scanning: false,
    scanningPlatforms: [] as ScanningPlatform[],
    scanStats: {
      scanned_platforms: 0,
      new_platforms: 0,
      identified_platforms: 0,
      scanned_roms: 0,
      added_roms: 0,
      identified_roms: 0,
    },
  }),

  actions: {
    set(scanning: boolean) {
      this.scanning = scanning;
    },
    reset() {
      this.scanning = false;
      this.scanningPlatforms = [] as ScanningPlatform[];
      this.scanStats = {
        scanned_platforms: 0,
        new_platforms: 0,
        identified_platforms: 0,
        scanned_roms: 0,
        added_roms: 0,
        identified_roms: 0,
      };
    },
  },
});
