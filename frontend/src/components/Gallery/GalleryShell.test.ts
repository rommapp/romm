import { flushPromises, shallowMount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import { createMemoryHistory, createRouter } from "vue-router";
import type { GalleryItem } from "@/composables/useGalleryVirtualItems";
import { RVirtualScroller } from "@/lib";
import storeGalleryFilter from "@/stores/galleryFilter";
import storeGalleryRoms from "@/stores/galleryRoms";
import { romFixture } from "@/utils/rom.fixtures";
import GalleryShell from "./GalleryShell.vue";
import GameListRow from "./GameListRow.vue";

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

describe("GalleryShell search refresh", () => {
  it("closes an open list panel when a new result swaps in at the same count", async () => {
    const page = (ids: number[]) => ({
      data: {
        total: ids.length,
        items: ids.map((id) => romFixture({ id })),
        char_index: {},
        rom_id_index: ids,
      },
    });
    getRoms.mockResolvedValue(page([1, 2]));
    const galleryRoms = storeGalleryRoms();
    galleryRoms.currentSearch = true;
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: "/search", component: { template: "<div />" } }],
    });
    await router.push("/search?layout=list");
    const wrapper = shallowMount(GalleryShell, {
      props: { hasHeader: false, searchPlaceholder: "", emptyMessage: "" },
      global: {
        plugins: [router],
        stubs: {
          // Renders every item, so the list rows exist without a viewport.
          RVirtualScroller: {
            props: { items: { type: Array, required: true } },
            methods: { scrollTo() {} },
            template: `<div><template v-for="(item, index) in items" :key="index"><slot :item="item" :index="index" /></template></div>`,
          },
        },
      },
    });
    await galleryRoms.refreshResults();
    await flushPromises();

    const firstRow = () => wrapper.findAllComponents(GameListRow)[0]!;
    firstRow().vm.$emit("toggle-expand");
    await flushPromises();
    expect(firstRow().props("expanded")).toBe(true);

    getRoms.mockResolvedValue(page([3, 4]));
    storeGalleryFilter().searchTerm = "zelda";
    await flushPromises();

    expect(galleryRoms.getRomAt(0)?.id).toBe(3);
    expect(firstRow().props("expanded")).toBe(false);
  });
});
