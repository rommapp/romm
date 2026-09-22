import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it } from "vitest";
import storeGalleryFilter from "@/stores/galleryFilter";

describe("galleryFilter filter option lists", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
  });

  it("coerces null or undefined API lists to empty arrays", () => {
    const store = storeGalleryFilter();
    store.setFilterGenres(["RPG"]);
    store.setFilterGenres(null);
    expect(store.filterGenres).toEqual([]);

    store.setFilterTags(["Retro"]);
    store.setFilterTags(undefined);
    expect(store.filterTags).toEqual([]);
  });
});
