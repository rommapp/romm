import { defineStore } from "pinia";
import { ROUTES } from "@/plugins/router";

export type NavigationMode =
  | "systems"
  | "continuePlaying"
  | "collections"
  | "smartCollections"
  | "virtualCollections"
  | "controls";

export default defineStore("console", {
  state: () => ({
    platformIndex: 0,
    continuePlayingIndex: 0,
    collectionsIndex: 0,
    smartCollectionsIndex: 0,
    virtualCollectionsIndex: 0,
    controlIndex: 0,
    navigationMode: "systems" as NavigationMode,
    perPlatformGameIndex: {} as Record<number, number>,
    perCollectionGameIndex: {} as Record<number, number>,
    perSmartCollectionGameIndex: {} as Record<number, number>,
    perVirtualCollectionGameIndex: {} as Record<string, number>,
    perPlatformScrollTop: {} as Record<number, number>,
    perCollectionScrollTop: {} as Record<number, number>,
    perSmartCollectionScrollTop: {} as Record<number, number>,
    perVirtualCollectionScrollTop: {} as Record<string, number>,
  }),
  getters: {
    consoleMode: (state) => {
      // @ts-expect-error PiniaCustomProperties
      const { name } = state.$router.currentRoute.value;
      return (
        name === ROUTES.CONSOLE_HOME ||
        name === ROUTES.CONSOLE_PLATFORM ||
        name === ROUTES.CONSOLE_COLLECTION ||
        name === ROUTES.CONSOLE_SMART_COLLECTION ||
        name === ROUTES.CONSOLE_VIRTUAL_COLLECTION ||
        name === ROUTES.CONSOLE_ROM ||
        name === ROUTES.CONSOLE_PLAY
      );
    },
  },
  actions: {
    setHomeState(payload: {
      platformIndex?: number;
      continuePlayingIndex?: number;
      collectionsIndex?: number;
      smartCollectionsIndex?: number;
      virtualCollectionsIndex?: number;
      controlIndex?: number;
      navigationMode?: NavigationMode;
    }) {
      if (payload.platformIndex !== undefined)
        this.platformIndex = payload.platformIndex;
      if (payload.continuePlayingIndex !== undefined)
        this.continuePlayingIndex = payload.continuePlayingIndex;
      if (payload.collectionsIndex !== undefined)
        this.collectionsIndex = payload.collectionsIndex;
      if (payload.smartCollectionsIndex !== undefined)
        this.smartCollectionsIndex = payload.smartCollectionsIndex;
      if (payload.virtualCollectionsIndex !== undefined)
        this.virtualCollectionsIndex = payload.virtualCollectionsIndex;
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
    setSmartCollectionGameIndex(smartCollectionId: number, idx: number) {
      this.perSmartCollectionGameIndex[smartCollectionId] = idx;
    },
    getSmartCollectionGameIndex(smartCollectionId: number) {
      return this.perSmartCollectionGameIndex[smartCollectionId] ?? 0;
    },
    setVirtualCollectionGameIndex(virtualCollectionId: string, idx: number) {
      this.perVirtualCollectionGameIndex[virtualCollectionId] = idx;
    },
    getVirtualCollectionGameIndex(virtualCollectionId: string) {
      return this.perVirtualCollectionGameIndex[virtualCollectionId] ?? 0;
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
    setSmartCollectionScroll(smartCollectionId: number, top: number) {
      this.perSmartCollectionScrollTop[smartCollectionId] = top;
    },
    getSmartCollectionScroll(smartCollectionId: number) {
      return this.perSmartCollectionScrollTop[smartCollectionId] ?? 0;
    },
    setVirtualCollectionScroll(virtualCollectionId: string, top: number) {
      this.perVirtualCollectionScrollTop[virtualCollectionId] = top;
    },
    getVirtualCollectionScroll(virtualCollectionId: string) {
      return this.perVirtualCollectionScrollTop[virtualCollectionId] ?? 0;
    },
  },
});
