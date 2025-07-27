import type {
  CollectionSchema,
  VirtualCollectionSchema,
  SmartCollectionSchema,
} from "@/__generated__";
import { uniqBy } from "lodash";
import { defineStore } from "pinia";
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
    favoriteCollection: {} as Collection | undefined,
    filterText: "" as string,
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
