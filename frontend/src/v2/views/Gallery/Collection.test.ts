/* eslint-disable vue/one-component-per-file */
import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { defineComponent, ref } from "vue";
import storeCollections, {
  type Collection,
  type SmartCollection,
  type VirtualCollection,
} from "@/stores/collections";
import type { SimpleRom } from "@/stores/roms";
import storeGalleryRoms from "@/v2/stores/galleryRoms";
import CollectionView from "./Collection.vue";

const {
  getRandomRom,
  getRoms,
  push,
  routeGuards,
  snackbarError,
  snackbarInfo,
} = vi.hoisted(() => ({
  getRandomRom: vi.fn(),
  getRoms: vi.fn(),
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
  default: { deleteCollection: vi.fn() },
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
    emits: ["random"],
    template: `<header><button class="random" @click="$emit('random')" /></header>`,
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
