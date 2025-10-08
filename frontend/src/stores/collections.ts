import { uniqBy } from "lodash";
import { defineStore } from "pinia";
import type {
  CollectionSchema,
  VirtualCollectionSchema,
  SmartCollectionSchema,
} from "@/__generated__";
import collectionApi from "@/services/api/collection";
import type { SimpleRom } from "./roms";

export type Collection = CollectionSchema;
export type VirtualCollection = VirtualCollectionSchema;
export type SmartCollection = SmartCollectionSchema;
export type CollectionType = Collection | VirtualCollection | SmartCollection;

export default defineStore("collections", {
  state: () => ({
    allCollections: [] as Collection[],
    virtualCollections: [] as VirtualCollection[],
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
          });
      });
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
      this.smartCollections = [];
      this.favoriteCollection = undefined;
      this.filterText = "";
    },
  },
});
