/* eslint-disable vue/one-component-per-file */
import { flushPromises, mount } from "@vue/test-utils";
import { AxiosError } from "axios";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { defineComponent, nextTick, ref } from "vue";
import storeCollections, {
  type Collection,
  type SmartCollection,
  type VirtualCollection,
} from "@/stores/collections";
import type { SimpleRom } from "@/stores/roms";
import storeGalleryRoms from "@/v2/stores/galleryRoms";
import CollectionView from "./Collection.vue";

const {
  getCollection,
  getRandomRom,
  getRoms,
  getVirtualCollection,
  push,
  routeGuards,
  snackbarError,
  snackbarInfo,
} = vi.hoisted(() => ({
  getCollection: vi.fn(),
  getRandomRom: vi.fn(),
  getRoms: vi.fn(),
  getVirtualCollection: vi.fn(),
  push: vi.fn(),
  routeGuards: [] as ((to: {
    name: string;
    params: Record<string, string>;
  }) => unknown)[],
  snackbarError: vi.fn(),
  snackbarInfo: vi.fn(),
}));

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

const { routeState } = vi.hoisted(() => ({
  routeState: {
    name: "collection",
    path: "/collection/1",
    params: { collection: "1" } as Record<string, string>,
    query: {} as Record<string, string>,
  },
}));

vi.mock("vue-router", async (importOriginal) => ({
  ...(await importOriginal<typeof import("vue-router")>()),
  useRoute: () => routeState,
  useRouter: () => ({ push, replace: vi.fn() }),
  // Captured rather than dropped: calling the guard is how a test moves
  // the view to another collection, which is what the stale check watches.
  onBeforeRouteUpdate: vi.fn((guard) => routeGuards.push(guard)),
}));

vi.mock("@/plugins/router", () => ({
  ROUTES: { ROM: "rom", COLLECTIONS: "collections" },
}));

vi.mock("@/services/api/rom", () => ({
  default: { getRandomRom, getRoms, bulkDownloadRoms: vi.fn() },
}));

vi.mock("@/services/api/collection", () => ({
  default: {
    deleteCollection: vi.fn(),
    getCollection,
    getVirtualCollection,
    getSmartCollection: vi.fn(),
  },
}));

vi.mock("@v2/lib", () => ({
  RDivider: defineComponent({ template: "<hr />" }),
}));

vi.mock("@/v2/components/Gallery/GalleryShell.vue", () => ({
  default: defineComponent({
    setup(_props, { expose }) {
      expose({ applyRestoredScroll: vi.fn() });
    },
    template: "<main><slot name='header' /></main>",
  }),
}));

vi.mock("@/v2/components/Gallery/CollectionHead.vue", () => ({
  default: defineComponent({
    props: { collection: { type: Object, default: null } },
    emits: ["random"],
    template: `<header><span class="rom-count">{{ collection?.rom_count }}</span><button class="random" @click="$emit('random')" /></header>`,
  }),
}));

vi.mock("@/v2/components/Gallery/CollectionSettingsTab.vue", () => ({
  default: defineComponent({ template: "<div />" }),
}));

vi.mock("@/v2/composables/useCan", () => ({
  useCan: () => ref(true),
}));

vi.mock("@/v2/composables/useConfirm", () => ({
  useConfirm: () => vi.fn().mockResolvedValue(false),
}));

vi.mock("@/v2/composables/usePageTitle", () => ({
  usePageTitle: vi.fn(),
}));

vi.mock("@/v2/composables/useSnackbar", () => ({
  useSnackbar: () => ({ error: snackbarError, info: snackbarInfo }),
}));

vi.mock("@/v2/composables/useWebpSupport", () => ({
  useWebpSupport: () => ({
    supportsWebp: ref(false),
    toWebp: (url: string) => url,
  }),
}));

function collection(id: number): Collection {
  return { id, name: `Collection ${id}`, rom_count: 9000 } as Collection;
}

function virtualCollection(romCount: number): VirtualCollection {
  return {
    id: "collection-zelda",
    name: "The Legend of Zelda",
    rom_count: romCount,
  } as VirtualCollection;
}

function rom(id: number): SimpleRom {
  return { id, name: "Chrono Trigger" } as SimpleRom;
}

async function mountView() {
  const galleryRoms = storeGalleryRoms();
  vi.spyOn(galleryRoms, "fetchInitialMetadata").mockResolvedValue();

  const wrapper = mount(CollectionView);
  await flushPromises();
  // Only what the button does is under test, not the view's own load flow.
  getRoms.mockClear();
  return wrapper;
}

describe("Collection view random rom", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
    routeGuards.length = 0;
    routeState.name = "collection";
    routeState.params = { collection: "1" };
    getRoms.mockResolvedValue({ data: { items: [], total: 0 } });
    getCollection.mockImplementation((id: number) =>
      Promise.resolve({ data: collection(id) }),
    );
    storeCollections().setCollections([collection(1), collection(2)]);
  });

  it("resolves a pick with a single scoped request", async () => {
    // Issue #4068: the pick used to cost a count request plus a fetch at a
    // random offset, and a scoped request is never cached, so the whole
    // collection was re-walked on every click.
    getRandomRom.mockResolvedValue({ data: rom(42) });

    const wrapper = await mountView();
    await wrapper.get("button.random").trigger("click");
    await flushPromises();

    expect(getRandomRom).toHaveBeenCalledTimes(1);
    expect(getRandomRom).toHaveBeenCalledWith({ collectionId: 1 });
    expect(getRoms).not.toHaveBeenCalled();
    expect(push).toHaveBeenCalledWith({ name: "rom", params: { rom: 42 } });
  });

  it("scopes the pick to a virtual collection", async () => {
    routeState.name = "virtual-collection";
    routeState.params = { collection: "genre-rpg" };
    storeCollections().setVirtualCollections([
      { id: "genre-rpg", name: "RPG", rom_count: 12 } as VirtualCollection,
    ]);
    getRandomRom.mockResolvedValue({ data: rom(7) });

    const wrapper = await mountView();
    await wrapper.get("button.random").trigger("click");
    await flushPromises();

    expect(getRandomRom).toHaveBeenCalledWith({
      virtualCollectionId: "genre-rpg",
    });
  });

  it("scopes the pick to a smart collection", async () => {
    routeState.name = "smart-collection";
    routeState.params = { collection: "5" };
    storeCollections().setSmartCollection([
      { id: 5, name: "Unplayed", rom_count: 12 } as SmartCollection,
    ]);
    getRandomRom.mockResolvedValue({ data: rom(7) });

    const wrapper = await mountView();
    await wrapper.get("button.random").trigger("click");
    await flushPromises();

    expect(getRandomRom).toHaveBeenCalledWith({ smartCollectionId: 5 });
  });

  it("reports an empty collection without navigating", async () => {
    getRandomRom.mockResolvedValue({ data: null });

    const wrapper = await mountView();
    await wrapper.get("button.random").trigger("click");
    await flushPromises();

    expect(snackbarInfo).toHaveBeenCalledWith("collection.empty");
    expect(push).not.toHaveBeenCalled();
  });

  it("reports a failed pick without navigating", async () => {
    getRandomRom.mockRejectedValue(new Error("boom"));

    const wrapper = await mountView();
    await wrapper.get("button.random").trigger("click");
    await flushPromises();

    expect(snackbarError).toHaveBeenCalledWith("platform.random-rom-error");
    expect(push).not.toHaveBeenCalled();
  });

  it("drops a pick that lands after the view moved to another collection", async () => {
    let resolvePick: (value: { data: SimpleRom }) => void = () => {};
    getRandomRom.mockReturnValue(
      new Promise((resolve) => {
        resolvePick = resolve;
      }),
    );

    const wrapper = await mountView();
    await wrapper.get("button.random").trigger("click");

    routeState.params = { collection: "2" };
    routeGuards.forEach((guard) =>
      guard({ name: "collection", params: { collection: "2" } }),
    );
    await flushPromises();

    resolvePick({ data: rom(42) });
    await flushPromises();

    // The pick belongs to the collection the user left, so following it
    // would drop them into a game from a gallery they closed.
    expect(push).not.toHaveBeenCalled();
  });

  it("stays quiet when a pick fails after the view moved to another collection", async () => {
    let failPick: (reason: Error) => void = () => {};
    getRandomRom.mockReturnValueOnce(
      new Promise((_resolve, reject) => {
        failPick = reject;
      }),
    );

    const wrapper = await mountView();
    await wrapper.get("button.random").trigger("click");

    routeState.params = { collection: "2" };
    routeGuards.forEach((guard) =>
      guard({ name: "collection", params: { collection: "2" } }),
    );
    await flushPromises();

    failPick(new Error("boom"));
    await flushPromises();

    expect(snackbarError).not.toHaveBeenCalled();
    expect(push).not.toHaveBeenCalled();

    // The button still works on the collection the user landed on.
    getRandomRom.mockResolvedValue({ data: rom(7) });
    await wrapper.get("button.random").trigger("click");
    await flushPromises();

    expect(push).toHaveBeenCalledWith({ name: "rom", params: { rom: 7 } });
  });

  // Issue #4114: leaving for a route that is not another gallery leaves
  // `currentCollection` set, so the id check alone cannot tell that the user
  // walked away.
  it("drops a pick that lands after the user left the gallery", async () => {
    let resolvePick: (value: { data: SimpleRom }) => void = () => {};
    getRandomRom.mockReturnValueOnce(
      new Promise((resolve) => {
        resolvePick = resolve;
      }),
    );

    const wrapper = await mountView();
    await wrapper.get("button.random").trigger("click");

    wrapper.unmount();

    resolvePick({ data: rom(42) });
    await flushPromises();

    expect(push).not.toHaveBeenCalled();
  });

  it("stays quiet when a pick fails after the user left the gallery", async () => {
    let failPick: (reason: Error) => void = () => {};
    getRandomRom.mockReturnValueOnce(
      new Promise((_resolve, reject) => {
        failPick = reject;
      }),
    );

    const wrapper = await mountView();
    await wrapper.get("button.random").trigger("click");

    wrapper.unmount();

    failPick(new Error("boom"));
    await flushPromises();

    expect(snackbarError).not.toHaveBeenCalled();
    expect(push).not.toHaveBeenCalled();
  });

  it("ignores a click while a pick is in flight", async () => {
    let resolvePick: (value: { data: SimpleRom }) => void = () => {};
    getRandomRom.mockReturnValue(
      new Promise((resolve) => {
        resolvePick = resolve;
      }),
    );

    const wrapper = await mountView();
    await wrapper.get("button.random").trigger("click");
    await wrapper.get("button.random").trigger("click");

    expect(getRandomRom).toHaveBeenCalledTimes(1);

    resolvePick({ data: rom(42) });
    await flushPromises();
    expect(push).toHaveBeenCalledTimes(1);
  });
});

// The store's lists load once per session, so a cached ROM count disagrees
// with the gallery below it.
describe("Collection view freshness", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
    routeGuards.length = 0;
    routeState.name = "collection";
    routeState.params = { collection: "1" };
    getRoms.mockResolvedValue({ data: { items: [], total: 0 } });
    getCollection.mockImplementation((id: number) =>
      Promise.resolve({ data: collection(id) }),
    );
    // `collection()` caches 9000 ROMs, so any other count came from the server.
    storeCollections().setCollections([collection(1)]);
  });

  it("renders the count the server returns, not the cached one", async () => {
    getCollection.mockResolvedValue({
      data: { ...collection(1), rom_count: 12 },
    });

    const wrapper = await mountView();

    expect(getCollection).toHaveBeenCalledWith(1);
    expect(wrapper.get(".rom-count").text()).toBe("12");
  });

  it("re-reads the virtual collection being opened", async () => {
    routeState.name = "virtual-collection";
    routeState.params = { collection: "collection-zelda" };
    storeCollections().setVirtualCollections([virtualCollection(4)]);
    getVirtualCollection.mockResolvedValue({ data: virtualCollection(5) });

    const wrapper = await mountView();

    expect(getVirtualCollection).toHaveBeenCalledWith("collection-zelda");
    expect(wrapper.get(".rom-count").text()).toBe("5");
  });

  // What a finished scan does: the store refetches, and the open page has to
  // follow it.
  it("adopts the store's copy when a refresh replaces it", async () => {
    routeState.name = "virtual-collection";
    routeState.params = { collection: "collection-zelda" };
    const collections = storeCollections();
    collections.setVirtualCollections([virtualCollection(4)]);
    getVirtualCollection.mockResolvedValue({ data: virtualCollection(4) });

    const wrapper = await mountView();
    collections.setVirtualCollections([virtualCollection(5)]);
    await nextTick();

    expect(wrapper.get(".rom-count").text()).toBe("5");
  });

  it("ignores a read that lands after the route moved on", async () => {
    let settleFirst!: (value: { data: Collection }) => void;
    getCollection.mockReturnValueOnce(
      new Promise((resolve) => {
        settleFirst = resolve;
      }),
    );

    const galleryRoms = storeGalleryRoms();
    vi.spyOn(galleryRoms, "fetchInitialMetadata").mockResolvedValue();
    const wrapper = mount(CollectionView);

    routeState.params = { collection: "2" };
    getCollection.mockResolvedValueOnce({
      data: { ...collection(2), rom_count: 22 },
    });
    await routeGuards[0]?.({ name: "collection", params: { collection: "2" } });
    await flushPromises();

    settleFirst({ data: { ...collection(1), rom_count: 11 } });
    await flushPromises();

    expect(wrapper.get(".rom-count").text()).toBe("22");
  });

  // A 404 answers, unlike a failed read, so the cached copy must not keep a
  // deleted collection on screen.
  it("shows not-found when the server says the collection is gone", async () => {
    getCollection.mockRejectedValue(
      Object.assign(new AxiosError("HTTP 404"), { response: { status: 404 } }),
    );

    const wrapper = await mountView();

    expect(wrapper.find(".rom-count").exists()).toBe(false);
    expect(storeCollections().allCollections).toEqual([]);
  });

  it("falls back to the cached copy when the re-read fails", async () => {
    getCollection.mockRejectedValue(new Error("offline"));

    const wrapper = await mountView();

    expect(wrapper.get(".rom-count").text()).toBe("9000");
  });
});
