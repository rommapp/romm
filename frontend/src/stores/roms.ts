import { defineStore } from "pinia";
import type {
  DetailedRomSchema,
  SimpleRomSchema,
  SearchRomSchema,
} from "@/__generated__/";
import cachedApiService from "@/services/cache/api";

export type SimpleRom = SimpleRomSchema;
export type SearchRom = SearchRomSchema;
export type DetailedRom = DetailedRomSchema;

// The page on screen, the game a navigation is loading, and one to spare for
// the player view that picks up the details page's record.
export const DETAILED_ROM_CACHE_SIZE = 3;

export default defineStore("roms", {
  state: () => ({
    currentRom: null as DetailedRom | null,
    recentRoms: [] as SimpleRom[],
    continuePlayingRoms: [] as SimpleRom[],
    /** Detailed ROMs by id, most recently cached last. */
    detailedRoms: new Map<number, DetailedRom>(),
  }),

  getters: {
    getDetailedRom: (state) => (id: number) =>
      state.detailedRoms.get(id) ?? null,
  },

  actions: {
    setCurrentRom(rom: DetailedRom) {
      this.currentRom = rom;
      this.cacheDetailedRom(rom);
    },
    cacheDetailedRom(rom: DetailedRom) {
      this.detailedRoms.delete(rom.id);
      this.detailedRoms.set(rom.id, rom);
      if (this.detailedRoms.size > DETAILED_ROM_CACHE_SIZE) {
        const oldest = this.detailedRoms.keys().next().value;
        if (oldest !== undefined) this.detailedRoms.delete(oldest);
      }
    },
    /** Drop records for games that no longer exist. */
    forgetDetailedRoms(ids: number[]) {
      for (const id of ids) this.detailedRoms.delete(id);
    },
    /** Spread `rom` over the cached record so its detailed-only fields
     * survive a SimpleRom write. */
    mergeIntoDetailedRom(rom: SimpleRom) {
      if (this.currentRom?.id === rom.id) {
        this.currentRom = { ...this.currentRom, ...rom };
      }
      const cached = this.detailedRoms.get(rom.id);
      if (cached) this.detailedRoms.set(rom.id, { ...cached, ...rom });
    },
    setRecentRoms(roms: SimpleRom[]) {
      this.recentRoms = roms;
    },
    setContinuePlayingRoms(roms: SimpleRom[]) {
      this.continuePlayingRoms = roms;
    },
    // Recent ROMs for home page
    async fetchRecentRoms(): Promise<SimpleRom[]> {
      const response = await cachedApiService.getRecentRoms((data) => {
        this.setRecentRoms(data.items);
      });
      const { items } = response.data;
      this.setRecentRoms(items);
      return items;
    },
    // Continue playing ROMs for home page
    async fetchContinuePlayingRoms(): Promise<SimpleRom[]> {
      const response = await cachedApiService.getRecentPlayedRoms((data) => {
        this.setContinuePlayingRoms(data.items);
      });
      const { items } = response.data;
      this.setContinuePlayingRoms(items);
      return items;
    },
    addToRecent(rom: SimpleRom) {
      this.recentRoms = [rom, ...this.recentRoms];
      void cachedApiService.clearRecentRomsCache();
    },
    removeFromRecent(rom: SimpleRom) {
      this.recentRoms = this.recentRoms.filter((value) => value.id !== rom.id);
      void cachedApiService.clearRecentRomsCache();
    },
    addToContinuePlaying(rom: SimpleRom) {
      this.continuePlayingRoms = [rom, ...this.continuePlayingRoms];
      void cachedApiService.clearRecentPlayedRomsCache();
    },
    removeFromContinuePlaying(rom: SimpleRom) {
      this.continuePlayingRoms = this.continuePlayingRoms.filter(
        (value) => value.id !== rom.id,
      );
      void cachedApiService.clearRecentPlayedRomsCache();
    },
    update(rom: SimpleRom) {
      this.recentRoms = this.recentRoms.map((value) =>
        value.id === rom.id ? rom : value,
      );
      this.continuePlayingRoms = this.continuePlayingRoms.map((value) =>
        value.id === rom.id ? rom : value,
      );
      // A gallery toggle (status, favourite) would otherwise leave the detail
      // view on stale `rom_user` data until the next route entry.
      this.mergeIntoDetailedRom(rom);
    },
    // Logout calls `reset` on every store.
    reset() {
      this.currentRom = null;
      this.detailedRoms.clear();
    },
  },
});
