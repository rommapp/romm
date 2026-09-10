import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { createMemoryHistory, createRouter, type Router } from "vue-router";
import type { SimpleRom } from "@/stores/roms";
import storeGallerySelection from "@/v2/stores/gallerySelection";
import GameCard from "./GameCard.vue";

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

function makeRom(id: number): SimpleRom {
  return {
    id,
    name: `Game ${id}`,
    fs_name_no_ext: `Game ${id}`,
    platform_slug: "snes",
    path_cover_large: null,
    path_cover_small: null,
    url_cover: null,
    regions: [],
    languages: [],
  } as unknown as SimpleRom;
}

function makeRouter(): Router {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: "/", component: { template: "<div />" } },
      { path: "/rom/:id", component: { template: "<div />" } },
    ],
  });
}

async function mountCard(rom: SimpleRom, router: Router) {
  await router.push("/");
  await router.isReady();
  return mount(GameCard, {
    props: { rom, selectable: true, position: 0 },
    global: { plugins: [router] },
  });
}

beforeEach(() => {
  setActivePinia(createPinia());
});

describe("GameCard selection", () => {
  it("navigates on a plain click when nothing is selected", async () => {
    const router = makeRouter();
    const wrapper = await mountCard(makeRom(1), router);

    await wrapper.find(".r-gc").trigger("click");
    await flushPromises();

    expect(router.currentRoute.value.fullPath).toBe("/rom/1");
    expect(storeGallerySelection().ids).toEqual([]);
  });

  it("toggles instead of navigating once the gallery is in selection mode", async () => {
    const selection = storeGallerySelection();
    selection.toggle(makeRom(2), 1);

    const router = makeRouter();
    const wrapper = await mountCard(makeRom(1), router);

    await wrapper.find(".r-gc").trigger("click");
    await flushPromises();

    expect(router.currentRoute.value.fullPath).toBe("/");
    expect(selection.ids).toEqual([2, 1]);
  });

  it("enters selection mode on a modifier click without navigating", async () => {
    const router = makeRouter();
    const wrapper = await mountCard(makeRom(1), router);

    await wrapper.find(".r-gc").trigger("click", { ctrlKey: true });
    await flushPromises();

    expect(router.currentRoute.value.fullPath).toBe("/");
    expect(storeGallerySelection().ids).toEqual([1]);
  });
});
