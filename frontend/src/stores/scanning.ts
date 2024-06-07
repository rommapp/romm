import { defineStore } from "pinia";
import type { SimpleRom } from "@/stores/roms";

export default defineStore("scanning", {
  state: () => ({
    scanning: false,
    scanningPlatforms: [] as {
      name: string;
      slug: string;
      id: number;
      roms: SimpleRom[];
    }[],
    scanStats: {
      scanned_platforms: 0,
      added_platforms: 0,
      metadata_platforms: 0,
      scanned_roms: 0,
      added_roms: 0,
      metadata_roms: 0,
    },
  }),

  actions: {
    set(scanning: boolean) {
      this.scanning = scanning;
    },
  },
});
