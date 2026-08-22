import axios from "axios";
import { uniqBy } from "lodash";
import { defineStore } from "pinia";
import type {
  CollectionSchema,
  VirtualCollectionSchema,
  SmartCollectionSchema,
} from "@/__generated__";
import collectionApi from "@/services/api/collection";
import storeAuth from "@/stores/auth";
import type { SimpleRom } from "./roms";

export type Collection = CollectionSchema;
export type VirtualCollection = VirtualCollectionSchema;
export type SmartCollection = SmartCollectionSchema;
export type CollectionType = Collection | VirtualCollection | SmartCollection;

/** A 404 or 403 answers the read (gone, or off limits); anything else means
 * the read never happened. */
function isGone(error: unknown): boolean {
  const status = axios.isAxiosError(error) ? error.response?.status : undefined;
  return status === 404 || status === 403;
}

export default defineStore("collections", {
  state: () => ({
    allCollections: [] as Collection[],
    virtualCollections: [] as VirtualCollection[],
    virtualCollectionType: null as string | null,
    virtualCollectionsStale: false as boolean,
    smartCollections: [] as SmartCollection[],
    favoriteCollection: undefined as Collection | undefined,
    filterText: "" as string,
    fetchingCollections: false as boolean,
    fetchingSmartCollections: false as boolean,
    fetchingVirtualCollections: false as boolean,
  }),
  getters: {
    filteredCollections: ({ allCollections, filterText }) =>
      allCollections.filter((p) =>
        p.name.toLowerCase().includes(filterText.toLowerCase()),
      ),
    ownedCollections: ({ allCollections }) => {
      const authStore = storeAuth();
      return allCollections.filter((c) => c.user_id === authStore.user?.id);
    },
    filteredVirtualCollections: ({ virtualCollections, filterText }) =>
      virtualCollections.filter((p) =>
        p.name.toLowerCase().includes(filterText.toLowerCase()),
      ),
    filteredSmartCollections: ({ smartCollections, filterText }) =>
      smartCollections.filter((p) =>
        p.name.toLowerCase().includes(filterText.toLowerCase()),
      ),
  },
  actions: {
    _reorderCollections() {
      this.allCollections = uniqBy(this.allCollections, "id").sort((a, b) => {
        return a.name.localeCompare(b.name);
      });
    },
    _reorderVirtualCollection() {
      this.virtualCollections = uniqBy(this.virtualCollections, "id").sort(
        (a, b) => {
          return a.name.localeCompare(b.name);
        },
      );
    },
    _reorderSmartCollections() {
      this.smartCollections = uniqBy(this.smartCollections, "id").sort(
        (a, b) => {
          return a.name.localeCompare(b.name);
        },
      );
    },
    fetchCollections(): Promise<Collection[]> {
      if (this.fetchingCollections) return Promise.resolve([]);
      this.fetchingCollections = true;

      return new Promise((resolve, reject) => {
        collectionApi
          .getCollections()
          .then(({ data: collections }) => {
            this.allCollections = collections;

            // Set the favorite collection
            const fav = collections.find((c) => c.is_favorite);
            if (fav) this.favoriteCollection = fav;

            resolve(collections);
          })
          .catch((error) => {
            console.error(error);
            reject(error);
          })
          .finally(() => {
            this.fetchingCollections = false;
          });
      });
    },
    fetchSmartCollections(): Promise<SmartCollection[]> {
      if (this.fetchingSmartCollections) return Promise.resolve([]);
      this.fetchingSmartCollections = true;

      return new Promise((resolve, reject) => {
        collectionApi
          .getSmartCollections()
          .then(({ data: smartCollections }) => {
            this.smartCollections = smartCollections;
            resolve(smartCollections);
          })
          .catch((error) => {
            console.error(error);
            reject(error);
          })
          .finally(() => {
            this.fetchingSmartCollections = false;
          });
      });
    },
    fetchVirtualCollections(type: string): Promise<VirtualCollection[]> {
      if (this.fetchingVirtualCollections) return Promise.resolve([]);
      this.fetchingVirtualCollections = true;
      this.virtualCollectionType = type;

      return new Promise((resolve, reject) => {
        collectionApi
          .getVirtualCollections({ type })
          .then(({ data: virtualCollections }) => {
            this.virtualCollections = virtualCollections;
            resolve(virtualCollections);
          })
          .catch((error) => {
            console.error(error);
            reject(error);
          })
          .finally(() => {
            this.fetchingVirtualCollections = false;
            if (this.virtualCollectionsStale) {
              this.virtualCollectionsStale = false;
              void this.refreshVirtualCollections();
            }
          });
      });
    },
    /** Re-read the loaded virtual collections, whose membership is derived
     * from ROM metadata that scans and matches rewrite. Never rejects: every
     * caller fires it in the background. */
    refreshVirtualCollections(): Promise<VirtualCollection[]> {
      const type = this.virtualCollectionType;
      if (type === null) return Promise.resolve([]);
      // A response already in flight left the server before the change did,
      // so queue the re-read behind it rather than let the guard drop it.
      if (this.fetchingVirtualCollections) {
        this.virtualCollectionsStale = true;
        return Promise.resolve([]);
      }
      return this.fetchVirtualCollections(type).catch(() => []);
    },
    /** Re-read one collection and refresh the cached copy. A gone collection
     * is dropped from the cache too, so callers read not-found from the cache
     * rather than from the null. */
    async refreshCollection(id: number): Promise<Collection | null> {
      try {
        const { data } = await collectionApi.getCollection(id);
        this.updateCollection(data);
        return data;
      } catch (error) {
        if (isGone(error)) {
          this.allCollections = this.allCollections.filter((c) => c.id !== id);
          if (this.favoriteCollection?.id === id) {
            this.favoriteCollection = undefined;
          }
        } else {
          console.error(error);
        }
        return null;
      }
    },
    async refreshVirtualCollection(
      id: string,
    ): Promise<VirtualCollection | null> {
      try {
        const { data } = await collectionApi.getVirtualCollection(id);
        this.updateVirtualCollection(data);
        return data;
      } catch (error) {
        if (isGone(error)) {
          this.virtualCollections = this.virtualCollections.filter(
            (c) => c.id !== id,
          );
        } else {
          console.error(error);
        }
        return null;
      }
    },
    async refreshSmartCollection(id: number): Promise<SmartCollection | null> {
      try {
        const { data } = await collectionApi.getSmartCollection(id);
        this.updateSmartCollection(data);
        return data;
      } catch (error) {
        if (isGone(error)) {
          this.smartCollections = this.smartCollections.filter(
            (c) => c.id !== id,
          );
        } else {
          console.error(error);
        }
        return null;
      }
    },
    setFavoriteCollection(favoriteCollection: Collection | undefined) {
      this.favoriteCollection = favoriteCollection;
    },
    setCollections(collections: Collection[]) {
      this.allCollections = collections;
    },
    setVirtualCollections(collections: VirtualCollection[]) {
      this.virtualCollections = collections;
    },
    setSmartCollection(collections: SmartCollection[]) {
      this.smartCollections = collections;
    },
    addCollection(collection: Collection) {
      this.allCollections.push(collection);
      this._reorderCollections();
    },
    addVirtualCollection(collection: VirtualCollection) {
      this.virtualCollections.push(collection);
      this._reorderVirtualCollection();
    },
    addSmartCollection(collection: SmartCollection) {
      this.smartCollections.push(collection);
      this._reorderSmartCollections();
    },
    updateCollection(collection: Collection) {
      this.allCollections = this.allCollections.map((value) =>
        value.id === collection.id ? collection : value,
      );
      this._reorderCollections();
    },
    // Replaces in place only: the list holds one virtual collection type, so
    // inserting could mix types.
    updateVirtualCollection(collection: VirtualCollection) {
      this.virtualCollections = this.virtualCollections.map((value) =>
        value.id === collection.id ? collection : value,
      );
    },
    updateSmartCollection(collection: SmartCollection) {
      this.smartCollections = this.smartCollections.map((value) =>
        value.id === collection.id ? collection : value,
      );
      this._reorderSmartCollections();
    },
    collectionExists(collection: Collection) {
      return (
        this.allCollections.filter((p) => p.name == collection.name).length > 0
      );
    },
    virtualCollectionExists(collection: VirtualCollection) {
      return (
        this.virtualCollections.filter((p) => p.name == collection.name)
          .length > 0
      );
    },
    smartCollectionExists(collection: SmartCollection) {
      return (
        this.smartCollections.filter((p) => p.name == collection.name).length >
        0
      );
    },
    removeCollection(collection: Collection) {
      this.allCollections = this.allCollections.filter((p) => {
        return p.name !== collection.name;
      });
    },
    removeVirtualCollection(collection: VirtualCollection) {
      this.virtualCollections = this.virtualCollections.filter((p) => {
        return p.name !== collection.name;
      });
    },
    removeSmartCollection(collection: SmartCollection) {
      this.smartCollections = this.smartCollections.filter((p) => {
        return p.name !== collection.name;
      });
    },
    getCollection(collectionId: number) {
      return this.allCollections.find((p) => p.id === collectionId);
    },
    getSmartCollection(smartCollectionId: number) {
      return this.smartCollections.find((p) => p.id === smartCollectionId);
    },
    getVirtualCollection(virtualCollectionId: string) {
      return this.virtualCollections.find((p) => p.id === virtualCollectionId);
    },
    isFavorite(rom: SimpleRom) {
      return this.favoriteCollection?.rom_ids?.includes(rom.id);
    },
    reset() {
      this.allCollections = [];
      this.virtualCollections = [];
      this.virtualCollectionType = null;
      this.virtualCollectionsStale = false;
      this.smartCollections = [];
      this.favoriteCollection = undefined;
      this.filterText = "";
    },
  },
});
