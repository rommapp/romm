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
import CollectionsIndex from "./CollectionsIndex.vue";

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

// Plain object rather than a reactive route: every test sets the query
// before mounting, which is when the view reads it.
const { routeState, routerState, searchState } = vi.hoisted(() => ({
  routeState: { query: {} as Record<string, string> },
  routerState: { replace: vi.fn() },
  searchState: { term: "" },
}));

vi.mock("vue-router", async (importOriginal) => ({
  ...(await importOriginal<typeof import("vue-router")>()),
  useRoute: () => routeState,
  useRouter: () => ({
    ...routerState,
    currentRoute: { value: routeState },
  }),
}));

vi.mock("@v2/lib", () => ({
  RDivider: defineComponent({ template: "<hr />" }),
  RIcon: defineComponent({ template: "<i />" }),
  RLetterHeading: defineComponent({
    props: { label: { type: String, default: "" } },
    template: "<h2>{{ label }}</h2>",
  }),
  RSkeletonBlock: defineComponent({ template: "<div />" }),
}));

// Captures the kind cluster so the "virtual option is gone" assertion
// reads the real toolbar payload instead of rendered markup.
const segmentFilterIds = ref<string[]>([]);
vi.mock("@/v2/components/Gallery/GalleryToolbar.vue", () => ({
  default: defineComponent({
    props: { segmentFilters: { type: Array, default: () => [] } },
    setup(props) {
      const filters = props.segmentFilters as {
        key: string;
        items: { id: string }[];
      }[];
      segmentFilterIds.value = (
        filters.find((f) => f.key === "kind")?.items ?? []
      ).map((i) => i.id);
      return () => null;
    },
  }),
}));

vi.mock("@/v2/components/Collections/CollectionListHeader.vue", () => ({
  default: defineComponent({ template: "<div />" }),
}));

vi.mock("@/v2/components/Collections/CollectionListRow.vue", () => ({
  default: defineComponent({
    props: { name: { type: String, default: "" } },
    template: '<div class="coll-row">{{ name }}</div>',
  }),
}));

vi.mock("@/v2/components/Collections/CollectionTile.vue", () => ({
  default: defineComponent({
    props: { name: { type: String, default: "" } },
    template: '<div class="coll-tile">{{ name }}</div>',
  }),
}));

vi.mock("@/v2/components/shared/EmptyState.vue", () => ({
  default: defineComponent({
    props: { message: { type: String, default: "" } },
    template: '<div class="empty-state">{{ message }}</div>',
  }),
}));

vi.mock("@/v2/components/shared/IndexShell.vue", () => ({
  default: defineComponent({
    template:
      '<main><slot name="header" /><slot name="toolbar" /><slot name="listHeader" /><slot /></main>',
  }),
}));

vi.mock("@/v2/components/shared/PageHeader.vue", () => ({
  default: defineComponent({
    props: {
      title: { type: String, default: "" },
      count: { type: Number, default: 0 },
    },
    template: "<header>{{ title }} {{ count }}</header>",
  }),
}));

vi.mock("@/v2/composables/useGalleryMode", () => ({
  useGalleryMode: () => ({ groupBy: ref("none"), layout: ref("grid") }),
}));

vi.mock("@/v2/composables/useGalleryViewModeUrl", () => ({
  useGalleryViewModeUrl: vi.fn(),
}));

vi.mock("@/v2/composables/useTileSearchUrl", () => ({
  useTileSearchUrl: () => ref(searchState.term),
}));

vi.mock("@/v2/composables/useWebpSupport", () => ({
  useWebpSupport: () => ({ toWebp: (url: string) => url }),
}));

vi.mock("@/v2/composables/useWrapGridNav", () => ({
  useWrapGridNav: vi.fn(),
}));

// Live ref rather than a per-call snapshot, so a test can flip the
// preference after mount the way the settings toggle does.
const showVirtualCollections = ref(false);
vi.mock("@/composables/useUISettings", () => ({
  useUISettings: () => ({
    showVirtualCollections,
    virtualCollectionType: ref("collection"),
  }),
}));

function collection(id: number, name: string): Collection {
  return { id, name, rom_count: 3, is_public: true } as Collection;
}

function smart(id: number, name: string): SmartCollection {
  return { id, name, rom_count: 2, is_public: true } as SmartCollection;
}

function virtual(id: string, name: string): VirtualCollection {
  return { id, name, rom_count: 5 } as VirtualCollection;
}

function seed() {
  const collections = storeCollections();
  collections.allCollections = [collection(1, "Favourites")];
  collections.smartCollections = [smart(2, "Recently Added")];
  collections.virtualCollections = [virtual("nintendo", "Nintendo")];
  return collections;
}

describe("CollectionsIndex", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    routeState.query = {};
    routerState.replace = vi.fn();
    searchState.term = "";
    showVirtualCollections.value = false;
    segmentFilterIds.value = [];
  });

  it("hides virtual collections when the setting is off", () => {
    seed();

    const wrapper = mount(CollectionsIndex);

    expect(wrapper.text()).toContain("Favourites");
    expect(wrapper.text()).toContain("Recently Added");
    expect(wrapper.text()).not.toContain("Nintendo");
    expect(wrapper.text()).toContain("common.collections 2");
  });

  it("shows virtual collections when the setting is on", () => {
    showVirtualCollections.value = true;
    seed();

    const wrapper = mount(CollectionsIndex);

    expect(wrapper.text()).toContain("Nintendo");
    expect(wrapper.text()).toContain("common.collections 3");
  });

  it("skips the virtual fetch on mount when the setting is off", () => {
    const collections = seed();
    collections.virtualCollections = [];
    const fetchVirtual = vi
      .spyOn(collections, "fetchVirtualCollections")
      .mockResolvedValue([]);

    mount(CollectionsIndex);

    expect(fetchVirtual).not.toHaveBeenCalled();
  });

  it("fetches virtual collections on mount when the setting is on", () => {
    showVirtualCollections.value = true;
    const collections = seed();
    collections.virtualCollections = [];
    const fetchVirtual = vi
      .spyOn(collections, "fetchVirtualCollections")
      .mockResolvedValue([]);

    mount(CollectionsIndex);

    expect(fetchVirtual).toHaveBeenCalledWith("collection");
  });

  it("drops the virtual option from the kind filter when the setting is off", () => {
    seed();

    mount(CollectionsIndex);

    expect(segmentFilterIds.value).toEqual(["all", "regular", "smart"]);
  });

  it("keeps the virtual option in the kind filter when the setting is on", () => {
    showVirtualCollections.value = true;
    seed();

    mount(CollectionsIndex);

    expect(segmentFilterIds.value).toEqual([
      "all",
      "regular",
      "smart",
      "virtual",
    ]);
  });

  it("falls back to all when ?kind=virtual arrives with the setting off", async () => {
    routeState.query = { kind: "virtual" };
    seed();

    const wrapper = mount(CollectionsIndex);
    await flushPromises();

    expect(wrapper.text()).toContain("Favourites");
    expect(wrapper.text()).toContain("Recently Added");
    expect(wrapper.text()).not.toContain("Nintendo");
    expect(routerState.replace).toHaveBeenCalledWith({ query: {} });
  });

  it("drops ?kind=virtual when the setting is turned off after mount", async () => {
    showVirtualCollections.value = true;
    routeState.query = { kind: "virtual" };
    seed();

    const wrapper = mount(CollectionsIndex);
    await flushPromises();
    expect(wrapper.text()).toContain("Nintendo");
    expect(routerState.replace).not.toHaveBeenCalled();

    showVirtualCollections.value = false;
    await flushPromises();

    expect(wrapper.text()).not.toContain("Nintendo");
    expect(wrapper.text()).toContain("Favourites");
    expect(routerState.replace).toHaveBeenCalledWith({ query: {} });
  });

  it("honors ?kind=virtual when the setting is on", () => {
    showVirtualCollections.value = true;
    routeState.query = { kind: "virtual" };
    seed();

    const wrapper = mount(CollectionsIndex);

    expect(wrapper.text()).toContain("Nintendo");
    expect(wrapper.text()).not.toContain("Favourites");
  });
});
