import { defineStore } from "pinia";
import type { CollectionSchema } from "@/__generated__";
import { uniqBy } from "lodash";

export type Collection = CollectionSchema;

export default defineStore("collections", {
  state: () => {
    return {
      all: [
        {
          name: "Favourites",
          description: "My favourites collection",
          rom_count: 10,
          id: 3,
        },
        {
          name: "Nintendo",
          description: "Nintendo collection",
          rom_count: 7,
          id: 1,
        },
        {
          name: "Sony",
          description: "Sony collection",
          rom_count: 20,
          id: 2,
        },
        {
          name: "Sega",
          description: "Sega collection",
          rom_count: 0,
          id: 2,
        },
        {
          name: "Favourites",
          description: "My favourites collection",
          rom_count: 10,
          id: 0,
        },
        {
          name: "Nintendo",
          description: "Nintendo collection",
          rom_count: 7,
          id: 1,
        },
        {
          name: "Sony",
          description: "Sony collection",
          rom_count: 20,
          id: 2,
        },
        {
          name: "Sega",
          description: "Sega collection",
          rom_count: 0,
          id: 2,
        },
        {
          name: "Favourites",
          description: "My favourites collection",
          rom_count: 10,
          id: 0,
        },
        {
          name: "Nintendo",
          description: "Nintendo collection",
          rom_count: 7,
          id: 1,
        },
        {
          name: "Sony",
          description: "Sony collection",
          rom_count: 20,
          id: 2,
        },
        {
          name: "Sega",
          description: "Sega collection",
          rom_count: 0,
          id: 2,
        },
        {
          name: "Favourites",
          description: "My favourites collection",
          rom_count: 10,
          id: 0,
        },
        {
          name: "Nintendo",
          description: "Nintendo collection",
          rom_count: 7,
          id: 1,
        },
        {
          name: "Sony",
          description: "Sony collection",
          rom_count: 20,
          id: 2,
        },
        {
          name: "Sega",
          description: "Sega collection",
          rom_count: 0,
          id: 2,
        },
      ] as Collection[],
      searchText: "" as string,
    };
  },
  getters: {
    totalGames: ({ all: value }) =>
      value.reduce((count, p) => count + p.rom_count, 0),
    filledCollections: ({ all }) => all.filter((p) => p.rom_count > 0),
    filteredCollections: ({ all, searchText }) =>
      all.filter(
        (p) =>
          p.rom_count > 0 &&
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
      // this._reorder();
    },
    exists(collection: Collection) {
      return this.all.filter((p) => p.fs_slug == collection.fs_slug).length > 0;
    },
    remove(collection: Collection) {
      this.all = this.all.filter((p) => {
        return p.slug !== collection.slug;
      });
    },
    get(collectionId: number) {
      return this.all.find((p) => p.id === collectionId);
    },
  },
});
