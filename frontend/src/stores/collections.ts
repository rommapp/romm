import { defineStore } from "pinia";
import type { CollectionSchema } from "@/__generated__";
import { uniqBy } from "lodash";

export type Collection = CollectionSchema;

export default defineStore("collections", {
  state: () => {
    return {
      all: [] as Collection[],
      searchText: "" as string,
    };
  },
  getters: {
    filteredCollections: ({ all, searchText }) =>
      all.filter((p) =>
        p.name.toLowerCase().includes(searchText.toLowerCase()),
      ),
  },
  actions: {
    _reorder() {
      this.all = this.all.sort((a, b) => {
        return a.name.localeCompare(b.name);
      });
      this.all = uniqBy(this.all, "id");
    },
    set(collections: Collection[]) {
      this.all = collections;
    },
    add(collection: Collection) {
      this.all.push(collection);
      this._reorder();
    },
    exists(collection: Collection) {
      return this.all.filter((p) => p.name == collection.name).length > 0;
    },
    remove(collection: Collection) {
      this.all = this.all.filter((p) => {
        return p.name !== collection.name;
      });
    },
    get(collectionId: number) {
      return this.all.find((p) => p.id === collectionId);
    },
  },
});
