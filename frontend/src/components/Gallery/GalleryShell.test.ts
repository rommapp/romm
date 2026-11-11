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

describe("GalleryShell re-sort", () => {
  it("keeps the result on screen while a re-sort refetches", async () => {
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
      global: { plugins: [router], stubs: { ViewportShell: false } },
    });
    await flushPromises();
    galleryRoms.total = 2;
    galleryRoms.metadataLoaded = true;
    galleryRoms.initialFetching = false;
    getRoms.mockClear();

    galleryRoms.setOrderDir("desc");
    await flushPromises();

    expect(galleryRoms.refreshing).toBe(true);
    expect(getRoms.mock.calls[0]![0].orderDir).toBe("desc");
    expect(scrollerItems(wrapper).some((i) => i.kind === "skeleton-row")).toBe(
      false,
    );
  });
});

describe("GalleryShell empty result", () => {
  it("keeps a known-empty result on screen through a refresh", async () => {
    getRoms.mockImplementation(() => new Promise(() => {}));
    const galleryRoms = storeGalleryRoms();
    galleryRoms.currentSearch = true;
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: "/search", component: { template: "<div />" } }],
    });
    await router.push("/search?search=zzz");
    const wrapper = shallowMount(GalleryShell, {
      props: { hasHeader: false, searchPlaceholder: "", emptyMessage: "" },
      global: { plugins: [router], stubs: { ViewportShell: false } },
    });
    await flushPromises();
    galleryRoms._resultRequest(0);
    galleryRoms.metadataLoaded = true;
    galleryRoms.initialFetching = false;
    await flushPromises();
    const empty = () =>
      scrollerItems(wrapper).find((i) => i.kind === "empty") as
        { message: string } | undefined;
    const before = empty()?.message;
    expect(before).toContain('"query":"zzz"');

    galleryRoms.setOrderDir("desc");
    storeGalleryFilter().searchTerm = "zzzz";
    await flushPromises();

    expect(galleryRoms.refreshing).toBe(true);
    expect(empty()?.message).toBe(before);
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
          ViewportShell: false,
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
