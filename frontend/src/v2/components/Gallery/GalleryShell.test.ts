import { flushPromises, shallowMount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import { defineComponent, type PropType } from "vue";
import { createMemoryHistory, createRouter } from "vue-router";
import { romFixture } from "@/utils/rom.fixtures";
import { GameCard } from "@/v2/components/GameCard";
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

describe("GalleryShell platform icons", () => {
  it.each<{ showPlatformBadge?: boolean; expected: boolean }>([
    { expected: true },
    { showPlatformBadge: true, expected: true },
    { showPlatformBadge: false, expected: false },
  ])(
    "forwards showPlatformBadge=$showPlatformBadge to cards",
    async ({ expected, ...props }) => {
      const galleryRoms = storeGalleryRoms();
      galleryRoms.total = 1;
      galleryRoms.byPosition.set(0, romFixture());
      const router = createRouter({
        history: createMemoryHistory(),
        routes: [{ path: "/search", component: { template: "<div />" } }],
      });
      await router.push("/search");
      const wrapper = shallowMount(GalleryShell, {
        props: {
          hasHeader: false,
          searchPlaceholder: "",
          emptyMessage: "",
          ...props,
        },
        global: {
          plugins: [router],
          renderStubDefaultSlot: true,
          stubs: {
            GameCard: false,
            RVirtualScroller: defineComponent({
              props: {
                items: {
                  type: Array as PropType<GalleryItem[]>,
                  required: true,
                },
              },
              template: `<div><slot v-for="(item, index) in items" :key="item.key" :item="item" :index="index" /></div>`,
            }),
          },
        },
      });

      const card = wrapper.getComponent(GameCard);
      expect(card.props("showPlatformIcon")).toBe(expected);
      expect(card.find(".r-gc__platform-icon").exists()).toBe(expected);
    },
  );
});

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
