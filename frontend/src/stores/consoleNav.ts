import { defineStore } from "pinia";

export const useConsoleNavStore = defineStore("consoleNav", {
  state: () => ({
    platformIndex: 0,
    recentIndex: 0,
    collectionsIndex: 0,
    controlIndex: 0,
    navigationMode: "systems" as
      | "systems"
      | "recent"
      | "collections"
      | "controls",
    perPlatformGameIndex: {} as Record<number, number>,
    perCollectionGameIndex: {} as Record<number, number>,
    perPlatformScrollTop: {} as Record<number, number>,
    perCollectionScrollTop: {} as Record<number, number>,
  }),
  actions: {
    setHomeState(payload: {
      platformIndex?: number;
      recentIndex?: number;
      collectionsIndex?: number;
      controlIndex?: number;
      navigationMode?: "systems" | "recent" | "collections" | "controls";
    }) {
      if (payload.platformIndex !== undefined)
        this.platformIndex = payload.platformIndex;
      if (payload.recentIndex !== undefined)
        this.recentIndex = payload.recentIndex;
      if (payload.collectionsIndex !== undefined)
        this.collectionsIndex = payload.collectionsIndex;
      if (payload.controlIndex !== undefined)
        this.controlIndex = payload.controlIndex;
      if (payload.navigationMode !== undefined)
        this.navigationMode = payload.navigationMode;
    },
    setPlatformGameIndex(platformId: number, idx: number) {
      this.perPlatformGameIndex[platformId] = idx;
    },
    getPlatformGameIndex(platformId: number) {
      return this.perPlatformGameIndex[platformId] ?? 0;
    },
    setCollectionGameIndex(collectionId: number, idx: number) {
      this.perCollectionGameIndex[collectionId] = idx;
    },
    getCollectionGameIndex(collectionId: number) {
      return this.perCollectionGameIndex[collectionId] ?? 0;
    },
    setPlatformScroll(platformId: number, top: number) {
      this.perPlatformScrollTop[platformId] = top;
    },
    getPlatformScroll(platformId: number) {
      return this.perPlatformScrollTop[platformId] ?? 0;
    },
    setCollectionScroll(collectionId: number, top: number) {
      this.perCollectionScrollTop[collectionId] = top;
    },
    getCollectionScroll(collectionId: number) {
      return this.perCollectionScrollTop[collectionId] ?? 0;
    },
  },
});
