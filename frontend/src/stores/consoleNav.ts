import { defineStore } from 'pinia';

export const useConsoleNavStore = defineStore('consoleNav', {
  state: () => ({
    platformIndex: 0,
    recentIndex: 0,
    collectionsIndex: 0,
    controlIndex: 0,
    navigationMode: 'systems' as 'systems'|'recent'|'collections'|'controls',
    perPlatformGameIndex: {} as Record<number, number>,
  }),
  actions: {
    setHomeState(payload: { platformIndex?: number; recentIndex?: number; collectionsIndex?: number; controlIndex?: number; navigationMode?: 'systems'|'recent'|'collections'|'controls'; }) {
      if(payload.platformIndex !== undefined) this.platformIndex = payload.platformIndex;
      if(payload.recentIndex !== undefined) this.recentIndex = payload.recentIndex;
      if(payload.collectionsIndex !== undefined) this.collectionsIndex = payload.collectionsIndex;
      if(payload.controlIndex !== undefined) this.controlIndex = payload.controlIndex;
      if(payload.navigationMode !== undefined) this.navigationMode = payload.navigationMode;
    },
    setPlatformGameIndex(platformId: number, idx: number){
      this.perPlatformGameIndex[platformId] = idx;
    },
    getPlatformGameIndex(platformId: number){
      return this.perPlatformGameIndex[platformId] ?? 0;
    },
  }
});
