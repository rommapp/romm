import type {
  CollectionSchema,
  VirtualCollectionSchema,
} from "@/__generated__";
import type { SmartCollectionSchema } from "@/services/api/collection";
import collectionApi from "@/services/api/collection";
import { uniqBy } from "lodash";
import { defineStore } from "pinia";
import type { SimpleRom } from "./roms";

export type Collection = CollectionSchema;
export type VirtualCollection = VirtualCollectionSchema;
export type SmartCollection = SmartCollectionSchema;

export default defineStore("collections", {
  state: () => ({
    allCollections: [] as Collection[],
    virtualCollections: [] as VirtualCollection[],
    smartCollections: [] as SmartCollection[],
    favCollection: {} as Collection | undefined,
    currentSmartCollection: null as SmartCollection | null,
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
    // Combine all collection types for unified display
    allCollectionsUnified: ({ allCollections, smartCollections }) => [
      ...allCollections,
      ...smartCollections,
    ],
    filteredCollectionsUnified: (state) => {
      const unified = [...state.allCollections, ...state.smartCollections];
      return unified.filter((p: Collection | SmartCollection) =>
        p.name.toLowerCase().includes(state.filterText.toLowerCase()),
      );
    },
  },
  actions: {
    _reorder() {
      this.allCollections = uniqBy(this.allCollections, "id").sort((a, b) => {
        return a.name.localeCompare(b.name);
      });
    },
    setFavCollection(favCollection: Collection | undefined) {
      this.favCollection = favCollection;
    },
    set(collections: Collection[]) {
      this.allCollections = collections;
    },
    setVirtual(collections: VirtualCollection[]) {
      this.virtualCollections = collections;
    },
    add(collection: Collection) {
      this.allCollections.push(collection);
      this._reorder();
    },
    update(collection: Collection) {
      this.allCollections = this.allCollections.map((value) =>
        value.id === collection.id ? collection : value,
      );
      this._reorder();
    },
    exists(collection: Collection) {
      return (
        this.allCollections.filter((p) => p.name == collection.name).length > 0
      );
    },
    remove(collection: Collection) {
      this.allCollections = this.allCollections.filter((p) => {
        return p.name !== collection.name;
      });
    },
    get(collectionId: number) {
      return this.allCollections.find((p) => p.id === collectionId);
    },
    isFav(rom: SimpleRom) {
      return this.favCollection?.rom_ids?.includes(rom.id);
    },
    // Smart collections actions
    setSmartCollections(smartCollections: SmartCollection[]) {
      this.smartCollections = smartCollections;
    },
    setCurrentSmartCollection(smartCollection: SmartCollection | null) {
      this.currentSmartCollection = smartCollection;
    },
    addSmartCollection(smartCollection: SmartCollection) {
      this.smartCollections.push(smartCollection);
      this.smartCollections.sort((a, b) => a.name.localeCompare(b.name));
    },
    updateSmartCollection(updatedSmartCollection: SmartCollection) {
      const index = this.smartCollections.findIndex(
        (sc) => sc.id === updatedSmartCollection.id,
      );
      if (index !== -1) {
        this.smartCollections[index] = updatedSmartCollection;
        this.smartCollections.sort((a, b) => a.name.localeCompare(b.name));
      }
    },
    removeSmartCollection(smartCollectionId: number) {
      const index = this.smartCollections.findIndex(
        (sc) => sc.id === smartCollectionId,
      );
      if (index !== -1) {
        this.smartCollections.splice(index, 1);
      }
    },
    getSmartCollection(collectionId: number) {
      return this.smartCollections.find((p) => p.id === collectionId);
    },
    // API actions for smart collections
    async fetchSmartCollections() {
      return collectionApi
        .getSmartCollections()
        .then(({ data }) => {
          this.setSmartCollections(data);
          return data;
        })
        .catch((error) => {
          console.error("Failed to fetch smart collections:", error);
          throw error;
        });
    },
    async fetchSmartCollectionById(id: number) {
      return collectionApi
        .getSmartCollection(id)
        .then(({ data }) => {
          this.setCurrentSmartCollection(data);
          return data;
        })
        .catch((error) => {
          console.error(`Failed to fetch smart collection ${id}:`, error);
          throw error;
        });
    },
    async createSmartCollection(params: {
      name: string;
      description?: string;
      filter_criteria: Record<string, any>;
      url_cover?: string;
      is_public?: boolean;
      artwork?: File;
    }) {
      return collectionApi
        .createSmartCollection(params)
        .then(({ data }) => {
          this.addSmartCollection(data);
          return data;
        })
        .catch((error) => {
          console.error("Failed to create smart collection:", error);
          throw error;
        });
    },
    async updateSmartCollectionById(
      id: number,
      params: {
        name?: string;
        description?: string;
        filter_criteria?: Record<string, any>;
        url_cover?: string;
        is_public?: boolean;
        remove_cover?: boolean;
        artwork?: File;
      },
    ) {
      return collectionApi
        .updateSmartCollection(id, params)
        .then(({ data }) => {
          this.updateSmartCollection(data);
          if (this.currentSmartCollection?.id === id) {
            this.setCurrentSmartCollection(data);
          }
          return data;
        })
        .catch((error) => {
          console.error(`Failed to update smart collection ${id}:`, error);
          throw error;
        });
    },
    async deleteSmartCollectionById(id: number) {
      return collectionApi
        .deleteSmartCollection(id)
        .then(({ data }) => {
          this.removeSmartCollection(id);
          if (this.currentSmartCollection?.id === id) {
            this.setCurrentSmartCollection(null);
          }
          return data;
        })
        .catch((error) => {
          console.error(`Failed to delete smart collection ${id}:`, error);
          throw error;
        });
    },
    reset() {
      this.allCollections = [];
      this.virtualCollections = [];
      this.smartCollections = [];
      this.favCollection = undefined;
      this.currentSmartCollection = null;
      this.filterText = "";
    },
  },
});
