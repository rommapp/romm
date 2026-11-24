import { flushPromises, mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import { defineComponent } from "vue";
import { createMemoryHistory, createRouter } from "vue-router";
import storeGalleryFilter from "@/stores/galleryFilter";
import storePlatforms from "@/stores/platforms";
import { platformFixture } from "@/utils/platform.fixtures";
import { useGalleryFilterUrl } from "./index";

async function mountAt(path: string) {
  storePlatforms().set([platformFixture({ id: 3 })]);
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
  await flushPromises();
  return router;
}

describe("useGalleryFilterUrl platforms logic", () => {
  it("reads an exclusion from the URL", async () => {
    await mountAt("/search?platforms=3&platformsLogic=none");

    expect(storeGalleryFilter().platformsLogic).toBe("none");
  });

  it("includes the platforms of a link that names no logic", async () => {
    const router = await mountAt("/search?platforms=3&platformsLogic=none");

    await router.push("/search?platforms=3");
    await flushPromises();

    expect(storeGalleryFilter().platformsLogic).toBe("any");
  });

  it("keeps a toggle picked before any platform", async () => {
    const router = await mountAt("/search");
    storeGalleryFilter().setPlatformsLogic("none");

    await router.push("/search?search=mario");
    await flushPromises();

    expect(storeGalleryFilter().platformsLogic).toBe("none");
  });
});
