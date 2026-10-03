import { flushPromises, shallowMount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import { createMemoryHistory, createRouter } from "vue-router";
import type { GalleryItem } from "@/v2/composables/useGalleryVirtualItems";
import { RVirtualScroller } from "@/v2/lib";
import storeGalleryRoms from "@/v2/stores/galleryRoms";
import GalleryShell from "./GalleryShell.vue";

const { getRoms } = vi.hoisted(() => ({ getRoms: vi.fn() }));

vi.mock("vue-i18n");

vi.mock("vue-router", async (importOriginal) => ({
  ...(await importOriginal<typeof import("vue-router")>()),
  onBeforeRouteUpdate: vi.fn(),
  onBeforeRouteLeave: vi.fn(),
}));

vi.mock("@/services/api/rom", () => ({ default: { getRoms } }));

function scrollerItems(wrapper: ReturnType<typeof shallowMount>) {
  return wrapper
    .findComponent(RVirtualScroller)
    .props("items") as GalleryItem[];
}

describe("GalleryShell re-sort skeleton", () => {
  it("paints only the known count while a re-sort refetches", async () => {
    getRoms.mockImplementation(() => new Promise(() => {}));
    const galleryRoms = storeGalleryRoms();
    galleryRoms.currentSearch = true;
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: "/search", component: { template: "<div />" } }],
    });
    await router.push("/search");
    const wrapper = shallowMount(GalleryShell, {
      props: { hasHeader: false, searchPlaceholder: "", emptyMessage: "" },
      global: { plugins: [router] },
    });
    await flushPromises();
    galleryRoms.total = 2;
    galleryRoms.metadataLoaded = true;
    galleryRoms.initialFetching = false;

    galleryRoms.setOrderDir("desc");
    await flushPromises();

    const cards = scrollerItems(wrapper).reduce(
      (n, i) => n + (i.kind === "skeleton-row" ? i.cards : 0),
      0,
    );
    expect(cards).toBe(2);
  });
});
