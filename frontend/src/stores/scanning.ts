import { defineStore } from "pinia";
import type { Rom } from "@/stores/roms";

export default defineStore("scanning", {
  state: () => ({
    scanning: false,
    scanningPlatforms: [] as {
      name: string;
      slug: string;
      id: number;
      roms: Rom[];
    }[],
  }),

  actions: {
    set(scanning: boolean) {
      this.scanning = scanning;
    },
  },
});
