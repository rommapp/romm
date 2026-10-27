import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import { defineComponent, nextTick } from "vue";
import { createMemoryHistory, createRouter } from "vue-router";
import storeGalleryFilter from "@/stores/galleryFilter";
import { useGalleryFilterUrl } from "./index";

async function mountAt(path: string) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: "/search", component: { render: () => null } }],
  });
  await router.push(path);
  mount(
    defineComponent({
      setup() {
        useGalleryFilterUrl();
        return () => null;
      },
    }),
    { global: { plugins: [router] } },
  );
  return router;
}

describe("useGalleryFilterUrl", () => {
  it("reads values without an operator as matching any of them", async () => {
    const filter = storeGalleryFilter();
    filter.setSelectedFilterReleaseTypes(["hack"]);
    filter.setReleaseTypesLogic("none");

    await mountAt("/search?releaseTypes=hack");

    expect(filter.selectedReleaseTypes).toEqual(["hack"]);
    expect(filter.releaseTypesLogic).toBe("any");
  });

  it("applies the operator the URL names", async () => {
    const filter = storeGalleryFilter();

    await mountAt("/search?genres=RPG&genresLogic=none");

    expect(filter.selectedGenres).toEqual(["RPG"]);
    expect(filter.genresLogic).toBe("none");
  });

  it("keeps an operator picked before any value when another filter changes", async () => {
    const filter = storeGalleryFilter();
    const router = await mountAt("/search");
    filter.setTagsLogic("none");

    await router.push("/search?genres=RPG");
    await nextTick();

    expect(filter.selectedGenres).toEqual(["RPG"]);
    expect(filter.tagsLogic).toBe("none");
  });
});
